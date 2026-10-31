"""Independent-source DC values, AC phasors and transient waveforms."""
import math


def dc_value(el) -> float:
    """DC value used by operating-point and AC bias calculations.

    SPICE waveform sources have a separate DC specification (default 0). The
    optional ``dc_value`` field preserves that distinction; circuits created by
    the canvas keep the historical behaviour where ``value`` is also the DC
    value.
    """
    return el.value if el.dc_value is None else el.dc_value


def ac_amplitude(el) -> float:
    return el.ac_amplitude if el.ac_amplitude is not None else dc_value(el)


def evaluate_source(el, t: float | None) -> float:
    if t is None or el.source_waveform == 'dc':
        return dc_value(el)
    if el.source_waveform == 'sine':
        amplitude = el.sine_amplitude
        if amplitude is None:
            amplitude = el.ac_amplitude if el.ac_amplitude is not None else dc_value(el)
        phase = el.sine_phase if el.sine_phase is not None else el.ac_phase
        delay = el.sine_delay
        if t < delay:
            return el.sine_offset
        elapsed = t - delay
        envelope = math.exp(-el.sine_damping * elapsed) if el.sine_damping else 1.0
        return el.sine_offset + envelope * amplitude * math.sin(
            2 * math.pi * (el.sine_frequency or 60) * elapsed + math.radians(phase)
        )
    if el.source_waveform == 'step':
        return el.value if t > 0 else 0.0
    if el.source_waveform == 'pulse':
        if t < el.pulse_delay:
            return el.pulse_low
        period = el.pulse_period or 1.0
        width = el.pulse_width if el.pulse_width is not None else period / 2
        elapsed = (t - el.pulse_delay) % period
        if el.pulse_rise and elapsed < el.pulse_rise:
            return el.pulse_low + (el.value - el.pulse_low) * elapsed / el.pulse_rise
        elapsed -= el.pulse_rise
        if elapsed < width:
            return el.value
        elapsed -= width
        if el.pulse_fall and elapsed < el.pulse_fall:
            return el.value + (el.pulse_low - el.value) * elapsed / el.pulse_fall
        return el.pulse_low
    raise ValueError(f'Unsupported source waveform: {el.source_waveform}')
