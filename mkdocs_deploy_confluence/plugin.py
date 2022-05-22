import os
import sys

import mkdocs.config.config_options
import mkdocs.plugins
from loguru import logger
from mkdocs.config import Config
from mkdocs.structure.files import Files
from mkdocs.structure.pages import Page
from mkdocs_deploy_confluence.site_builder import SiteBuilder

LOGGER_FORMAT = "<lvl>{level:8}</lvl> - <cyan>[Confluence:{function}():{line}]</cyan> {message}"

logger.remove()
logger.add(sys.stderr, format=LOGGER_FORMAT, level="DEBUG")


# noinspection PyMethodMayBeStatic
class DeployConfluence(mkdocs.plugins.BasePlugin):
    enabled = True
    site_builder: SiteBuilder = None
    config_scheme = (
        ("url", mkdocs.config.config_options.Type(str, default=None)),
        ("space", mkdocs.config.config_options.Type(str, default=None)),
        ("debug", mkdocs.config.config_options.Type(bool, default=True)),
        ("parent_page", mkdocs.config.config_options.Type(str, default=None)),
    )

    def on_config(self, config: Config):
        config_ok = True
        self.config["bearer-token"] = os.environ.get("CONFLUENCE_BEARER_TOKEN", None)
        if not self.config["bearer-token"]:
            config_ok = False
            logger.warning("Missing beaerer token in environment CONFLUENCE_BEARER_TOKEN")
        if not self.config["url"]:
            config_ok = False
            logger.warning("Missing url configuration (e.g. https://confluence.example.com/rest/api)")
        if not self.config["space"]:
            config_ok = False
            logger.warning("Missing confluence space configuration")
        if not self.config["debug"]:
            logger.remove()
            logger.add(sys.stderr, format=LOGGER_FORMAT, level="INFO")
        if not config_ok:
            logger.warning("deploy_confluence plugin disabled because of configuration issues")
            self.enabled = False
        logger.debug("on_config done")
        return config

    def on_page_markdown(self, markdown: str, page: Page, config: Config, files: Files):
        if not self.enabled:
            return markdown
        if page.meta.get("confluence"):
            logger.info(f"uploading {page.title}")
            self.site_builder.add_page(markdown, page, config, files)
        else:
            logger.info(f"ignoring {page.title} because meta.confluene: false")

    def on_pre_build(self, config: Config):
        if not self.enabled:
            return
        self.site_builder = SiteBuilder(config=self.config)
