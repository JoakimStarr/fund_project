import os
import yaml
from pathlib import Path
from dotenv import load_dotenv


class Settings:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        load_dotenv()
        PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
        config_path = PROJECT_ROOT / "config.yaml"
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        self.app = cfg["app"]
        self.data = cfg["data"]
        self.feature = cfg["feature"]
        self.screening = cfg["screening"]
        self.model = cfg["model"]
        self.interval = cfg["interval"]
        self.nav_constraints = cfg["nav_constraints"]
        self.bond = cfg["bond"]
        self.cold_start = cfg["cold_start"]
        self.ai_provider = cfg["ai_provider"]
        self.news_service = cfg["news_service"]
        self.task = cfg["task"]
        self.api = cfg["api"]
        self.scheduler = cfg["scheduler"]
        self.logging = cfg["logging"]
        self.glm_api_key = os.getenv("GLM_API_KEY", "")
        self.siliconflow_api_key = os.getenv("SILICONFLOW_API_KEY", "")

    @property
    def db_path(self):
        PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
        return str(PROJECT_ROOT / self.data["db_path"])


settings = Settings()