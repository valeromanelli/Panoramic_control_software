import numpy as np

from sequenciator import Sequenciator, SequenciatorJunior, SequenciatorThreshold


def test_complete_sequence_is_packed_as_uint32() -> None:
    generator = Sequenciator(1_000_000, 10.0, 20.0, {})
    generator.define_pre_ill_array(2)
    generator.define_pre_stim_array(2)
    generator.define_stim_array(2)
    generator.define_post_stim_array(2)

    waveform, shock = generator.define_array_to_send()

    assert waveform.dtype == np.uint32
    assert waveform.ndim == 1
    assert waveform.size > 2
    assert shock is False
    assert waveform[0] == 0
    assert waveform[-1] == 0


def test_junior_sequence_contains_four_dmd_groups() -> None:
    generator = SequenciatorJunior(10, 20, 30, 40, 50, 60, 70, 80, duration_ms=1)
    generator.enable_dmd1(True, False)
    generator.enable_dmd2(False, True)
    generator.enable_dmd3(True, True)
    generator.enable_dmd4(False, False)
    waveform = generator.define_array_to_send()

    assert waveform.dtype == np.uint32
    assert waveform.ndim == 1
    assert waveform.size > 0


def test_threshold_sequence_generation() -> None:
    generator = SequenciatorThreshold(2, 10, 4)
    waveform, scan_rate = generator.define_array_to_send(50)

    assert waveform.dtype == np.uint32
    assert waveform.ndim == 1
    assert scan_rate > 0
