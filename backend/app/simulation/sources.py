"""Independent-source DC values and transient waveforms."""
import math


def evaluate_source(el, t: float | None) -> float:
    if t is None or el.source_waveform == 'dc':
        return el.value
    if el.source_waveform == 'sine':
        amplitude = el.sine_amplitude
        if amplitude is None:
            amplitude = el.ac_amplitude if el.ac_amplitude is not None else el.value
        phase = el.sine_phase if el.sine_phase is not None else el.ac_phase
        return el.sine_offset + amplitude * math.sin(2 * math.pi * (el.sine_frequency or 60) * t + math.radians(phase))
    if el.source_waveform == 'step':
        return el.value if t > 0 else 0.0
    if el.source_waveform == 'pulse':
        if t < el.pulse_delay:
            return el.pulse_low
        period = el.pulse_period or 1.0
        width = el.pulse_width if el.pulse_width is not None else period / 2
        elapsed = (t - el.pulse_delay) % period
        if el.pulse_rise and elapsed < el.pulse_rise:
            return el.pulse_low + (el.value-el.pulse_low)*elapsed/el.pulse_rise
        elapsed -= el.pulse_rise
        if elapsed < width:
            return el.value
        elapsed -= width
        if el.pulse_fall and elapsed < el.pulse_fall:
            return el.value + (el.pulse_low-el.value)*elapsed/el.pulse_fall
        return el.pulse_low
    raise ValueError(f'Unsupported source waveform: {el.source_waveform}')
