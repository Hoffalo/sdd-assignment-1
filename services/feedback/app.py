"""Start command of the feedback service: python app.py"""
import logging

from waitress import serve

from avdesk_feedback.composition import create_app
from avdesk_feedback.config import get_config


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = get_config()
    # 0.0.0.0, not localhost: inside a container localhost is unreachable from outside it.
    serve(create_app(config), host="0.0.0.0", port=config.port)


if __name__ == "__main__":
    main()
