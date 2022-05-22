import os
import re
import sys
import zlib

import mistune
from atlassian import Confluence
from loguru import logger
from md2cf.confluence_renderer import ConfluenceRenderer
from mkdocs.config import Config
from mkdocs.structure.files import Files
from mkdocs.structure.pages import Page


def crc(file_name):
    prev = 0
    for eachLine in open(file_name, "rb"):
        prev = zlib.crc32(eachLine, prev)
    return "%X" % (prev & 0xFFFFFFFF)


class SiteBuilder:
    confluence: Confluence
    parent_page_id: int | None

    def __init__(self, config):
        self.space = config["space"]
        self.confluence = Confluence(url=config["url"], token=config["bearer-token"])

        if parent_page_title := config["parent_page"]:
            parent_page_id = self.confluence.get_page_id(space=self.space, title=parent_page_title)
            if not parent_page_id:
                logger.error(f"Parent-Page `{parent_page_title}` not found")
                sys.exit(1)
            self.parent_page_id = parent_page_id
        logger.debug("plugin initialized")

    def add_page(self, markdown: str, page: Page, config: Config, files: Files):
        renderer = ConfluenceRenderer(use_xhtml=True)
        confluence_mistune = mistune.Markdown(renderer=renderer)

        confluence_body = confluence_mistune(markdown)
        checksum = hex(zlib.crc32((page.title + confluence_body).encode(encoding="UTF8")))

        confluence_body = (
            "<ac:placeholder>Please don't edit this page manually, the content might get overwritten. "
            f"[{checksum}]</ac:placeholder>\n{confluence_body}"
        )

        if current_page := self.confluence.get_page_by_title(space=self.space, title=page.title, expand="body.storage"):
            try:
                current_checksum = re.findall(r". \[(.*)]<", current_page["body"]["storage"]["value"])[0]
            except IndexError:
                current_checksum = ""
            if current_checksum != checksum:
                logger.info(f"updateing page {page.file.src_path} '{page.title}'")
                self.confluence.update_page(
                    page_id=current_page["id"], title=page.title, body=confluence_body, parent_id=self.parent_page_id
                )
            else:
                logger.debug(f"not updating unchanged {page.file.src_path} '{page.title}'")
        else:
            current_page = self.confluence.create_page(
                space=self.space, title=page.title, body=confluence_body, parent_id=self.parent_page_id
            )
            logger.info(f"created new page [{current_page['id']}] {page.file.src_path} '{page.title}'")

        if len(renderer.attachments):
            attachment_list = {}
            for current_attachment in self.confluence.get_attachments_from_content(page_id=current_page["id"])["results"]:
                split = current_attachment["metadata"]["comment"].split(":")
                if len(split) == 2:
                    attachment_list[split[0]] = split[1]
            for attachment in renderer.attachments:
                filename = os.path.join(os.path.dirname(page.file.abs_src_path), attachment)
                checksum = crc(filename)
                if attachment_list.get(attachment) != checksum:
                    upl = self.confluence.attach_file(
                        page_id=current_page["id"], filename=filename, comment=f"{attachment}:{checksum}"
                    )
                    logger.info(f"uploaded attachment {attachment}")
                else:
                    logger.debug(f"unchanged attachment {attachment}")
