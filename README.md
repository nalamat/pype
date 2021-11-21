# Pype

The `Pype` module provides a generic, easy to use, and extendable object-oriented model for online processing of data streams in Python, which is particularly suited for handling multi-channel electrophysiology signals in the EARS software.

Inspired by the `dplyr` package in R, `Pype` allows definition of stream processing stages as `Node`s that can be connected to each other using `>>`, the shift operator. Alternatively, `|` or the shell pipe operator can be used.

```python
daqs.physiologyInput \
    >> pype.LFilter(fl=300, fh=6e3, n=6) \
    >> self.physiologyPlot
```

Here, a key difference with `dplyr` is that `>>` only declares the connections in the pipeline, but no actual processing of data occurs at this statement. All `Node`s inherit the `write()` method that when called, passes new data into the node for processing. The processed data will further be passed to the connected nodes downstream.

Normally data is processed synchronously in the pipeline, meaning the execution of the code goes on halt until all downstream nodes are done with their tasks. Although, a `Thread` node can be inserted into the pipeline to allow asynchronous processing of the data. This could prove useful in situations that the data acquisition thread must not be blocked for too long or when implementing an interactive GUI. Note that in the current implementation of `Thread`, due to limitations of Python's GIL, multithreaded code does not actually run in parallel, but asynchronously. If necessary, the `wait()` method can be called on the root node to block execution until an asynchronous pipeline is done processing.

```python
daqs.physiologyInput \
    >> pype.Thread() \
    >> pype.LFilter(fl=300, fh=6e3, n=6) \
    >> pype.GrandAverage() \
    >> pype.DownsampleMinMax(ds=32) \
    >> self.physiologyPlot
```

Other than linear pipelines, it is possible to connect nodes to multiple branches. This is done by applying `>>` between a node and an iterator of nodes. If the left hand side of `>>` has a single node, its output data will be passed to each of the nodes in the iterator in the order of appearance. In the following example, the same signal is filtered at different frequency bands and then passed on to different plots.

```python
daqs.physiologyInput \
    >> pype.Thread() \
    >> (pype.LFilter(fl=None, fh=300 , n=6) >> self.physiologyPlotLow,
        pype.LFilter(fl=300 , fh=6e3 , n=6) >> self.physiologyPlotMid,
        pype.LFilter(fl=6e3 , fh=None, n=6) >> self.physiologyPlotHigh)
```

Visualizations of pipeline structures are coming soon!

If instead of passing the same data to all downstream nodes, a splitting behavior is required, use the `Split` node between the source and the list of nodes. The code below passes spikes detected from each channel of the recorded signal to separate plots:

```python
daqs.physiologyInput \
    >> pype.Thread() \
    >> pype.LFilter(fl=300 , fh=6e3 , n=6) \
    >> pype.SpikeDetector() \
    >> pype.Split() \
    >> (self.spikePlot1, self.spikePlot2, self.spikePlot3)
```
