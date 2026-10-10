"""Single documented start command: python app.py"""
import logging

from waitress import serve

from avdesk.composition import create_app
from avdesk.config import get_config


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = get_config()
    # 0.0.0.0, not localhost: inside a container localhost is unreachable from the host (§7.2).
    serve(create_app(config), host="0.0.0.0", port=config.port)


if __name__ == "__main__":
    main()
