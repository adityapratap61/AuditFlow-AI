import logging


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level.upper())
        return
    logging.basicConfig(level=level.upper(), format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
