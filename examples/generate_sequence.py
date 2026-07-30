"""Generate an experiment waveform without communicating with NI-DAQ hardware."""

from pathlib import Path

import numpy as np

from sequenciator import Sequenciator


def main() -> None:
    generator = Sequenciator(
        scan_rate=10_000_000,
        red_duty_cycle=5.0,
        blue_duty_cycle=50.0,
        electrical_stimulation={},
    )
    generator.define_pre_ill_array(200)
    generator.define_pre_stim_array(200)
    generator.define_stim_array(1_000)
    generator.define_post_stim_array(200)

    waveform, includes_electrical_stimulation = generator.define_array_to_send()
    output_path = Path("example_waveform.npy")
    np.save(output_path, waveform)
    print(f"Saved {waveform.size} samples to {output_path}")
    print(f"Electrical stimulation included: {includes_electrical_stimulation}")


if __name__ == "__main__":
    main()
