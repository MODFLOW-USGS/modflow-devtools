# `timeit`

There is a `timeit` decorator function available in the `modflow_devtools.misc` module. Applying it to any function causes a (rough) runtime benchmark to be printed to `stdout` afterwards the function returns. For instance:

```python
@timeit
def sleep1():
    sleep(0.001)

sleep1() # prints e.g. "sleep1 took 1.26 ms"
```

`timeit` can also directly wrap a function:

```python
timeit(sleep1)() # prints same as above
```