"""Time-grid helpers: fixed-step grids and known source breakpoints."""
import math


def _collect_breakpoints(elements, settings):
    """Return (times, jumps) for source discontinuities and pulse interiors."""
    start, stop = settings.t_start, settings.t_stop
    times = {start, stop}
    jumps = {}

    def add(t, source=None, left=None):
        if start <= t <= stop:
            times.add(t)
            if source is not None:
                jumps.setdefault(t, {})[source.id] = left
        if len(times) > 200001:
            raise ValueError('Source breakpoints exceed 200000 transient steps; reduce duration or pulse frequency')

    for el in elements:
        if el.type not in ('voltage_source', 'current_source'):
            continue
        if el.source_waveform == 'step':
            add(0, el, 0.0)
        if el.source_waveform != 'pulse':
            continue
        period = el.pulse_period or 1.0
        width = el.pulse_width if el.pulse_width is not None else period / 2
        first = max(0, math.floor((start - el.pulse_delay) / period))
        last = math.floor((stop - el.pulse_delay) / period)
        if last - first > 200000:
            raise ValueError('Too many pulse periods for transient analysis')
        for cycle in range(first, last + 1):
            base = el.pulse_delay + cycle * period
            points = [base, base + el.pulse_rise, base + el.pulse_rise + width,
                      base + el.pulse_rise + width + el.pulse_fall, base + period]
            for point in points:
                add(point)
            # Retain at least one interior sample in each nonzero pulse segment.
            for a, b in zip(points, points[1:], strict=False):
                if b > a:
                    add(a + (b - a) / 2)
            if el.pulse_rise == 0:
                previous = el.value if cycle > 0 and width == period else el.pulse_low
                add(base, el, previous)
            if el.pulse_fall == 0:
                add(base + el.pulse_rise + width, el, el.value)
    return times, jumps


def _merge(times, jumps, start, stop):
    """Merge nearly-coincident times within floating-point resolution."""
    merged = []
    merged_jumps = {}
    for time in sorted(times):
        if merged and time - merged[-1] <= 4 * max(math.ulp(time), math.ulp(merged[-1])):
            previous = merged[-1]
            values = dict(merged_jumps.pop(previous, {}))
            for name, value in jumps.get(time, {}).items():
                if name in values and values[name] != value:
                    raise ValueError(f"Pulse edges for {name} are too close to resolve at t={time:g}")
                values[name] = value
            chosen = previous
            if previous != start and (time == stop or time in jumps):
                chosen = time
            merged[-1] = chosen
            if values:
                merged_jumps[chosen] = values
        else:
            merged.append(time)
            if time in jumps:
                merged_jumps[time] = dict(jumps[time])
    return merged, merged_jumps


def transient_grid(elements, settings):
    """Fixed-step grid (t_step) augmented with source breakpoints."""
    start, stop, step = settings.t_start, settings.t_stop, settings.t_step
    count = math.ceil((stop - start) / step)
    times, jumps = _collect_breakpoints(elements, settings)
    times.update(min(start + i * step, stop) for i in range(1, count + 1))
    return _merge(times, jumps, start, stop)


def transient_breakpoints(elements, settings):
    """Forced time points only (discontinuities and pulse interiors), no fixed grid."""
    times, jumps = _collect_breakpoints(elements, settings)
    return _merge(times, jumps, settings.t_start, settings.t_stop)
