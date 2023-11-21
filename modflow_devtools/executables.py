from pathlib import Path
from types import SimpleNamespace
from typing import Dict


class Executables(SimpleNamespace):
    """
    Container mapping executable names to their paths.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __setitem__(self, key, item):
        self.__dict__[key] = item

    def __getitem__(self, key):
        return self.__dict__[key]

    def get(self, key, default=None):
        return self.as_dict().get(key, default)

    def as_dict(self) -> Dict[str, Path]:
        """
        Returns a dictionary mapping executable names to paths.
        """

        return self.__dict__.copy()
