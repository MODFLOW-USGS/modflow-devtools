from types import SimpleNamespace


class Case(SimpleNamespace):
    """
    Minimal container for a reusable test case.
    """

    def __init__(self, case: "Case" = None, **kwargs):
        if case is not None:
            super().__init__(**case.__dict__.copy())
            return

        if "name" not in kwargs:
            raise ValueError(f"Case name is required")

        # set defaults
        if "xfail" not in kwargs:
            kwargs["xfail"] = False
        # if 'compare' not in kwargs:
        #     kwargs['compare'] = True

        super().__init__(**kwargs)

    def __repr__(self):
        return self.name

    def copy(self):
        """
        Copies the test case.
        """

        return Case(**self.__dict__.copy())

    def copy_update(self, **kwargs):
        """
        A utility method for copying a test case with changes.
        Recommended for dynamically generating similar cases.
        """

        cpy = self.__dict__.copy()
        cpy.update(kwargs)
        return Case(**cpy)
