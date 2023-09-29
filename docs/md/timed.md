# `timed`

There is a `@timed` decorator function available in the `modflow_devtools.misc` module. Applying it to any function prints a (rough) benchmark to `stdout` when the function returns. For instance:

```python
from modflow_devtools.misc import timed

@timed
def sleep1():
    sleep(0.001)

sleep1() # prints e.g. "sleep1 took 1.26 ms"
```

It can also wrap a function directly:

```python
timed(sleep1)()
```

The [`timeit`](https://docs.python.org/3/library/timeit.html) built-in module is used internally, however the timed function is only called once, where by default, `timeit` averages multiple runs.