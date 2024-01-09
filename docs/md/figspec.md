# Plot styles

Matplotlib is an optional dependency, installable via e.g. `pip install modflow_devtools[optional]`.

## `USGSFigure`

A convenience class `modflow_devtools.figspec.USGSFigure` is provided to create figures with the default USGS style sheet. For instance:

```python
# create figure
fs = USGSFigure(figure_type="graph", verbose=False)

# ...add some plots

# add a heading
title = f"Layer {ilay + 1}"
letter = chr(ord("@") + idx + 2)
fs.heading(letter=letter, heading=title)

# add an annotation
fs.add_annotation(
    ax=ax,
    text="Well 1, layer 2",
    bold=False,
    italic=False,
    xy=w1loc,
    xytext=(w1loc[0] - 3200, w1loc[1] + 1500),
    ha="right",
    va="center",
    zorder=100,
    arrowprops=arrow_props,
)
```