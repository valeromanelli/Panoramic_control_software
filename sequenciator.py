import nidaqmx
import numpy as np
import math
import matplotlib.pyplot as plt
from nidaqmx.constants import LineGrouping, AcquisitionType


class Sequenciator:
    def __init__(self, scan_rate, red_duty_cycle, blue_duty_cycle, electrical_stimulation):
        self.scan_rate = scan_rate
        self.point_interval = 1 / scan_rate
        self.electrical_stimulation = electrical_stimulation
        self.shock = True if self.electrical_stimulation else False
        red_duty_cycle = 0.01 * red_duty_cycle
        blue_duty_cycle = 0.01 * blue_duty_cycle

        self.frame_rate = 996.31
        self.period = 1 / self.frame_rate

        self.n_point_period = int(self.scan_rate * self.period)

        self.time_pre_ill = 0
        self.time_pre_stim = 0
        self.time_stim = 0
        self.time_post_stim = 0
        self.real_time_pre_ill = 0
        self.real_time_pre_stim = 0
        self.real_time_stim = 0
        self.real_time_post_stim = 0

        self.n_points_pre_ill = 0
        self.n_points_pre_stim = 0

        self.zero_points_cam = math.ceil(self.n_point_period / 2)
        self.one_points_cam = self.n_point_period - self.zero_points_cam
        vect_ones_cam = np.ones((1, self.one_points_cam))
        vect_zeros_cam = np.zeros((1, self.zero_points_cam))

        half_period_short = math.floor(self.n_point_period / 2)
        half_period_long = self.n_point_period - half_period_short

        # serve se i due semiperiodi sono a loro volta dispari altrimenti non tornano le dimensione dei vettori
        # il long si riferisce al semiperiod

        if half_period_long % 2 == 0:
            numb_long_l = int(half_period_long / 2)
            numb_long_h = int(half_period_long / 2)
        else:
            numb_long_l = math.floor(half_period_long / 2)
            numb_long_h = math.ceil(half_period_long / 2)

        # gli one sono corto perché abbiamo allungato il tempo in cui la camera è spenta
        if half_period_short % 2 == 0:
            numb_short_l = int(half_period_short / 2)
            numb_short_h = int(half_period_short / 2)
        else:
            numb_short_l = math.floor(half_period_short / 2)
            numb_short_h = math.ceil(half_period_short / 2)

        ones_short = np.ones((1, numb_short_l), dtype=np.uint8)
        zeros_short = np.zeros((1, numb_short_h), dtype=np.uint8)
        ones_long = np.ones((1, numb_long_l), dtype=np.uint8)
        zeros_long = np.zeros((1, numb_long_h), dtype=np.uint8)

        # RED
        # lo short è riferito al periodo
        numb_ones_points_red_short = math.ceil(half_period_short * red_duty_cycle)
        numb_zeros_points_red_short = half_period_short - numb_ones_points_red_short

        numb_ones_points_red_long  = math.ceil(half_period_long * red_duty_cycle)
        numb_zeros_points_red_long = half_period_long - numb_ones_points_red_long

        ones_points_red_short = np.ones((1, numb_ones_points_red_short), dtype=np.uint8)
        ones_points_red_long = np.ones((1, numb_ones_points_red_long), dtype=np.uint8)

        zeros_points_red_short = np.zeros((1, numb_zeros_points_red_short), dtype=np.uint8)
        zeros_points_red_long = np.zeros((1, numb_zeros_points_red_long), dtype=np.uint8)

        # BLU
        numb_ones_points_blue_short = math.ceil(half_period_short * blue_duty_cycle)
        numb_zeros_points_blue_short = half_period_short - numb_ones_points_blue_short

        numb_ones_points_blue_long = math.ceil(half_period_long * blue_duty_cycle)
        numb_zeros_points_blue_long = half_period_long - numb_ones_points_blue_long

        ones_points_blue_short = np.ones((1, numb_ones_points_blue_short), dtype=np.uint8)
        ones_points_blue_long = np.ones((1, numb_ones_points_blue_long), dtype=np.uint8)

        zeros_points_blue_short = np.zeros((1, numb_zeros_points_blue_short), dtype=np.uint8)
        zeros_points_blue_long = np.zeros((1, numb_zeros_points_blue_long), dtype=np.uint8)

        self.delay = 2310
        self.delay_red = int(numb_short_h - half_period_short * red_duty_cycle)
        self.conc_trig_cam = np.hstack((vect_ones_cam, vect_zeros_cam))
        self.conc_trig_patt = np.hstack((zeros_short, ones_short, zeros_long, ones_long)) #short e long è sempre riferito al periodo
        self.conc_trig_en_red = np.hstack((zeros_points_red_short, ones_points_red_short, zeros_points_red_long, ones_points_red_long))
        self.conc_trig_en_blue = np.hstack((ones_points_blue_short, zeros_points_blue_short, ones_points_blue_long, zeros_points_blue_long))

        self.array_cam = np.array([])
        self.array_trig_pattern = np.array([])
        self.array_en_red = np.array([])
        self.array_en_blue = np.array([])

    def define_pre_ill_array(self, time_pre_ill):
        self.time_pre_ill = time_pre_ill
        n_periods = math.ceil(time_pre_ill * 0.001 / self.period)
        self.n_points_pre_ill = n_periods * self.n_point_period
        self.real_time_pre_ill = n_periods * self.period

        trig_cam_pre_ill = np.zeros((4, self.n_points_pre_ill), dtype=np.uint8)
        trig_pattern_dmd_pre_ill = np.ones((4, self.n_points_pre_ill), dtype=np.uint8)
        en_red_led_dmd_pre_ill = np.tile(self.conc_trig_en_red, (4, n_periods))
        en_blue_led_dmd_pre_ill = np.zeros((4, self.n_points_pre_ill), dtype=np.uint8)

        self.array_cam = np.hstack((self.array_cam, trig_cam_pre_ill)) if self.array_cam.size else trig_cam_pre_ill
        self.array_trig_pattern = np.hstack((self.array_trig_pattern,trig_pattern_dmd_pre_ill)) if self.array_trig_pattern.size else trig_pattern_dmd_pre_ill
        self.array_en_red = np.hstack((self.array_en_red, en_red_led_dmd_pre_ill)) if self.array_en_red.size else en_red_led_dmd_pre_ill
        self.array_en_blue = np.hstack((self.array_en_blue, en_blue_led_dmd_pre_ill)) if self.array_en_blue.size else en_blue_led_dmd_pre_ill

        return self.real_time_pre_ill

    def define_pre_stim_array(self, time_pre_stim):
        self.time_pre_stim = time_pre_stim
        n_periods = math.ceil(time_pre_stim * 0.001 / self.period)
        print(n_periods)
        self.n_points_pre_stim = n_periods * self.n_point_period
        self.real_time_pre_stim = n_periods * self.period

        trig_cam_pre_stim = np.tile(self.conc_trig_cam, (4, n_periods))
        trig_pattern_dmd_pre_stim = np.ones((4, self.n_points_pre_stim), dtype=np.uint8)
        en_red_led_dmd_pre_stim = np.tile(self.conc_trig_en_red, (4, n_periods))
        en_blue_led_dmd_pre_stim = np.zeros((4, self.n_points_pre_stim), dtype=np.uint8)

        self.array_cam = np.hstack((self.array_cam, trig_cam_pre_stim)) if self.array_cam.size else trig_cam_pre_stim
        self.array_trig_pattern = np.hstack((self.array_trig_pattern, trig_pattern_dmd_pre_stim)) if self.array_trig_pattern.size else trig_pattern_dmd_pre_stim
        self.array_en_red = np.hstack((self.array_en_red, en_red_led_dmd_pre_stim)) if self.array_en_red.size else en_red_led_dmd_pre_stim
        self.array_en_blue = np.hstack((self.array_en_blue, en_blue_led_dmd_pre_stim)) if self.array_en_blue.size else en_blue_led_dmd_pre_stim

        return self.real_time_pre_stim

    def define_stim_array(self, time_stim):
        self.time_stim = time_stim
        n_periods = math.ceil(time_stim * 0.001 / self.period)
        print(n_periods)
        self.n_points_stim = n_periods * self.n_point_period
        self.real_time_stim = n_periods * self.period

        trig_cam_stim = np.tile(self.conc_trig_cam, (4, n_periods))
        trig_pattern_dmd_stim = np.tile(self.conc_trig_patt, (4, n_periods))
        en_red_led_dmd_stim = np.tile(self.conc_trig_en_red, (4, n_periods))
        en_blue_led_dmd_stim = np.tile(self.conc_trig_en_blue, (4, n_periods))

        self.array_cam = np.hstack((self.array_cam, trig_cam_stim)) if self.array_cam.size else trig_cam_stim
        self.array_trig_pattern = np.hstack((self.array_trig_pattern, trig_pattern_dmd_stim)) if self.array_trig_pattern.size else trig_pattern_dmd_stim
        self.array_en_red = np.hstack((self.array_en_red, en_red_led_dmd_stim)) if self.array_en_red.size else en_red_led_dmd_stim
        self.array_en_blue = np.hstack((self.array_en_blue, en_blue_led_dmd_stim)) if self.array_en_blue.size else en_blue_led_dmd_stim

        return self.real_time_stim

    def define_post_stim_array(self, time_post_stim):
        self.time_post_stim = time_post_stim
        n_periods = math.ceil(time_post_stim * 0.001 / self.period)
        print(n_periods)
        self.n_points_post_stim = n_periods * self.n_point_period
        self.real_time_post_stim = n_periods * self.period

        trig_cam_post_stim = np.tile(self.conc_trig_cam, (4, n_periods))
        trig_pattern_dmd_post_stim = np.ones((4, self.n_points_post_stim), dtype=np.uint8)
        en_red_led_dmd_post_stim = np.tile(self.conc_trig_en_red, (4, n_periods))
        en_blue_led_dmd_post_stim = np.zeros((4, self.n_points_post_stim), dtype=np.uint8)

        self.array_cam = np.hstack((self.array_cam, trig_cam_post_stim)) if self.array_cam.size else trig_cam_post_stim
        self.array_trig_pattern = np.hstack((self.array_trig_pattern, trig_pattern_dmd_post_stim)) if self.array_trig_pattern.size else trig_pattern_dmd_post_stim
        self.array_en_red = np.hstack((self.array_en_red, en_red_led_dmd_post_stim)) if self.array_en_red.size else en_red_led_dmd_post_stim
        self.array_en_blue = np.hstack((self.array_en_blue, en_blue_led_dmd_post_stim)) if self.array_en_blue.size else en_blue_led_dmd_post_stim

        return self.real_time_post_stim

    def define_array_to_send(self):
        delay_array = np.zeros((4, self.delay), dtype=np.uint8)
        delay_red_array = np.zeros((4, self.delay_red), dtype=np.uint8)

        array_trig_pattern_cut = self.array_trig_pattern[:, self.delay:]
        array_trig_pattern_cut = np.hstack((array_trig_pattern_cut, delay_array))

        array_en_red_delayed = self.array_en_red[:, self.delay_red:]
        array_en_red_delayed = np.hstack((array_en_red_delayed, delay_red_array))

        self.array_par = np.vstack((self.array_cam, array_trig_pattern_cut, array_en_red_delayed, self.array_en_blue))
        self.array_par = self.array_par.astype(np.uint8)
        if self.shock:
            array_shock = self.shocker(self.electrical_stimulation)
            array_shock = array_shock.astype(np.uint8)
            self.array_par = np.vstack((self.array_par, array_shock))
        array = self.array_par.T

        array_to_send = np.sum(array * (2 ** np.arange(0, array.shape[1], 1)), axis=1).astype(np.uint32)
        array_to_send = np.pad(array_to_send, pad_width=1, constant_values=0)

        return array_to_send, self.shock

    def shocker(self, dict):
        for key in dict.keys():
            if key == 'Constant':
                delay_points = int(dict[key][0] * 1e-3 * self.scan_rate)
                duration = dict[key][1] * 1e-3
                period = 1 / dict[key][2]
                n_points_high = int(period * self.scan_rate / 2)
                high_points = np.ones((1, n_points_high), dtype=np.uint8)
                low_points = np.zeros((1, n_points_high), dtype=np.uint8)
                conc_array = np.hstack((high_points, low_points))

                sequence = np.tile(conc_array, int(duration / period))

                array = np.zeros((1, delay_points), dtype=np.uint8)
                array = np.hstack((array, sequence))

                missing_points = self.array_par.shape[1] - array.shape[1]
                if missing_points > 0:
                    array = np.hstack((array, np.zeros((1, missing_points))))

            elif key == 'S1S2':
                values = dict[key][0]
                start_cl = values[0] / 1000
                pre_cond = dict[key][1]

                n_points_to_add = 0
                if self.n_points_pre_ill > 0:
                    n_points_to_add += self.n_points_pre_ill
                if self.n_points_pre_stim > 0:
                    n_points_to_add += self.n_points_pre_stim
                array = np.zeros((1, n_points_to_add), dtype=np.uint8)

                # S0
                n_points_high = int(start_cl * self.scan_rate / 2)
                high_points = np.ones((1, n_points_high), dtype=np.uint8)
                low_points = np.zeros((1, n_points_high), dtype=np.uint8)
                conc_array = np.hstack((high_points, low_points))
                sequence = np.tile(conc_array, pre_cond)

                # S1-Sn
                sn_values = values[1:]
                for value in sn_values:
                    cl = value / 1000
                    n_points_high = int(cl * self.scan_rate / 2)
                    high_points = np.ones((1, n_points_high), dtype=np.uint8)
                    low_points = np.zeros((1, n_points_high), dtype=np.uint8)
                    conc_array = np.hstack((high_points, low_points))
                    sequence = np.hstack((sequence, conc_array))

                array = np.hstack((array, sequence))
                missing_points = self.array_par.shape[1] - array.shape[1]
                if missing_points > 0:
                    array = np.hstack((array, np.zeros((1, missing_points))))

            elif key == "Ramp":
                cl_values = dict[key][0]
                numb_pulses = dict[key][1]

                array = np.zeros((1, 0))
                for value in cl_values:
                    cl = value / 1000
                    n_points_high = int(cl * self.scan_rate / 2)
                    high_points = np.ones((1, n_points_high), dtype=np.uint8)
                    low_points = np.zeros((1, n_points_high), dtype=np.uint8)
                    conc_array = np.hstack((high_points, low_points))
                    cl_array = np.tile(conc_array, numb_pulses)
                    array = np.hstack((array, cl_array))

                missing_points = self.array_par.shape[1] - array.shape[1]
                if missing_points > 0:
                    array = np.hstack((array, np.zeros((1, missing_points))))

        return array


class SequenciatorJunior:
    def __init__(self, dc_red_dmd1, dc_blue_dmd1, dc_red_dmd2, dc_blue_dmd2, dc_red_dmd3, dc_blue_dmd3, dc_red_dmd4, dc_blue_dmd4):
        self.scan_rate = 1000000
        self.scan_interval = 1 / self.scan_rate

        self.point_x_period = 500

        self.time = 60000
        self.numb_periods = int(2 * self.time)
        self.numb_points = int(self.numb_periods * self.point_x_period)

        self.dc_red_dmd1 = 0.01 * dc_red_dmd1
        self.dc_blue_dmd1 = 0.01 * dc_blue_dmd1
        self.dc_red_dmd2 = 0.01 * dc_red_dmd2
        self.dc_blue_dmd2 = 0.01 * dc_blue_dmd2
        self.dc_red_dmd3 = 0.01 * dc_red_dmd3
        self.dc_blue_dmd3 = 0.01 * dc_blue_dmd3
        self.dc_red_dmd4 = 0.01 * dc_red_dmd4
        self.dc_blue_dmd4 = 0.01 * dc_blue_dmd4

    def enable_dmd1(self, red, blue):
        if red:
            trig_dmd1 = np.ones((1, self.numb_points - 250))
            trig_dmd1 = np.hstack((np.zeros((1, 250)), trig_dmd1))

            high_red = int(self.point_x_period * self.dc_red_dmd1)
            low_red = int(self.point_x_period - high_red)
            period = np.hstack((np.zeros((1, low_red)), np.ones((1, high_red))))

            enable_red_dmd1 = np.tile(period, (1, self.numb_periods))
            enable_blue_dmd1 = np.zeros((1, self.numb_points))

        elif blue:
            trig_dmd1 = np.zeros((1, self.numb_points - 250))
            trig_dmd1 = np.hstack((np.ones((1, 250)), trig_dmd1))

            high_blue = int(self.point_x_period * self.dc_blue_dmd1)
            low_blue = int(self.point_x_period - high_blue)
            period = np.hstack((np.zeros((1, low_blue)), np.ones((1, high_blue))))

            enable_red_dmd1 = np.zeros((1, self.numb_points))
            enable_blue_dmd1 = np.tile(period, (1, self.numb_periods))

        else:
            trig_dmd1 = np.zeros((1, self.numb_points))
            enable_red_dmd1 = np.zeros((1, self.numb_points))
            enable_blue_dmd1 = np.zeros((1, self.numb_points))

        self.trig_dmd1 = trig_dmd1
        self.enable_red_dmd1 = enable_red_dmd1
        self.enable_blue_dmd1 = enable_blue_dmd1

    def enable_dmd2(self, red, blue):
        if red:
            trig_dmd2 = np.ones((1, self.numb_points - 250))
            trig_dmd2 = np.hstack((np.zeros((1, 250)), trig_dmd2))

            high_red = int(self.point_x_period * self.dc_red_dmd2)
            low_red = int(self.point_x_period - high_red)
            period = np.hstack((np.zeros((1, low_red)), np.ones((1, high_red))))

            enable_red_dmd2 = np.tile(period, (1, self.numb_periods))
            enable_blue_dmd2 = np.zeros((1, self.numb_points))

        elif blue:
            trig_dmd2 = np.zeros((1, self.numb_points - 250))
            trig_dmd2 = np.hstack((np.ones((1, 250)), trig_dmd2))

            high_blue = int(self.point_x_period * self.dc_blue_dmd2)
            low_blue = int(self.point_x_period - high_blue)
            period = np.hstack((np.zeros((1, low_blue)), np.ones((1, high_blue))))

            enable_red_dmd2 = np.zeros((1, self.numb_points))
            enable_blue_dmd2 = np.tile(period, (1, self.numb_periods))

        else:
            trig_dmd2 = np.zeros((1, self.numb_points))
            enable_red_dmd2 = np.zeros((1, self.numb_points))
            enable_blue_dmd2 = np.zeros((1, self.numb_points))

        self.trig_dmd2 = trig_dmd2
        self.enable_red_dmd2 = enable_red_dmd2
        self.enable_blue_dmd2 = enable_blue_dmd2

    def enable_dmd3(self, red, blue):
        if red:
            trig_dmd3 = np.ones((1, self.numb_points - 250))
            trig_dmd3 = np.hstack((np.zeros((1, 250)), trig_dmd3))

            high_red = int(self.point_x_period * self.dc_red_dmd3)
            low_red = int(self.point_x_period - high_red)
            period = np.hstack((np.zeros((1, low_red)), np.ones((1, high_red))))

            enable_red_dmd3 = np.tile(period, (1, self.numb_periods))
            enable_blue_dmd3 = np.zeros((1, self.numb_points))

        elif blue:
            trig_dmd3 = np.zeros((1, self.numb_points - 250))
            trig_dmd3 = np.hstack((np.ones((1, 250)), trig_dmd3))

            high_blue = int(self.point_x_period * self.dc_blue_dmd3)
            low_blue = int(self.point_x_period - high_blue)
            period = np.hstack((np.zeros((1, low_blue)), np.ones((1, high_blue))))

            enable_red_dmd3 = np.zeros((1, self.numb_points))
            enable_blue_dmd3 = np.tile(period, (1, self.numb_periods))

        else:
            trig_dmd3 = np.zeros((1, self.numb_points))
            enable_red_dmd3 = np.zeros((1, self.numb_points))
            enable_blue_dmd3 = np.zeros((1, self.numb_points))

        self.trig_dmd3 = trig_dmd3
        self.enable_red_dmd3 = enable_red_dmd3
        self.enable_blue_dmd3 = enable_blue_dmd3

    def enable_dmd4(self, red, blue):
        if red:
            trig_dmd4 = np.ones((1, self.numb_points - 250))
            trig_dmd4 = np.hstack((np.zeros((1, 250)), trig_dmd4))

            high_red = int(self.point_x_period * self.dc_red_dmd4)
            low_red = int(self.point_x_period - high_red)
            period = np.hstack((np.zeros((1, low_red)), np.ones((1, high_red))))

            enable_red_dmd4 = np.tile(period, (1, self.numb_periods))
            enable_blue_dmd4 = np.zeros((1, self.numb_points))

        elif blue:
            trig_dmd4 = np.zeros((1, self.numb_points - 250))
            trig_dmd4 = np.hstack((np.ones((1, 250)), trig_dmd4))

            high_blue = int(self.point_x_period * self.dc_blue_dmd4)
            low_blue = int(self.point_x_period - high_blue)
            period = np.hstack((np.zeros((1, low_blue)), np.ones((1, high_blue))))

            enable_red_dmd4 = np.zeros((1, self.numb_points))
            enable_blue_dmd4 = np.tile(period, (1, self.numb_periods))

        else:
            trig_dmd4 = np.zeros((1, self.numb_points))
            enable_red_dmd4 = np.zeros((1, self.numb_points))
            enable_blue_dmd4 = np.zeros((1, self.numb_points))

        self.trig_dmd4 = trig_dmd4
        self.enable_red_dmd4 = enable_red_dmd4
        self.enable_blue_dmd4 = enable_blue_dmd4

    def define_array_to_send(self):
        array = np.zeros((4, self.numb_points))

        array = np.vstack((array,
                            self.trig_dmd1, self.trig_dmd2, self.trig_dmd3, self.trig_dmd4,
                            self.enable_red_dmd1, self.enable_red_dmd2, self.enable_red_dmd3, self.enable_red_dmd4,
                            self.enable_blue_dmd1, self.enable_blue_dmd2, self.enable_blue_dmd3, self.enable_blue_dmd4))

        array_to_send = array.T

        array_to_send = np.sum(array_to_send * (2 ** np.arange(0, array_to_send.shape[1], 1)), axis=1).astype(np.uint32)
        array_to_send = np.pad(array_to_send, pad_width=1, constant_values=0)

        return array_to_send


class SequenciatorThreshold:
    def __init__(self, numb_cycles, frequency, cycle_duration):
        self.numb_cycles = numb_cycles
        self.frequency = frequency
        self.cycle_duration = round(0.001 * cycle_duration, 5)
        self.scan_rate = 10000000

        self.length_array = int(self.scan_rate * self.numb_cycles / self.frequency)

        trigger = np.zeros((self.length_array - 250, 4))
        self.pattern_trigger = np.vstack((np.ones((250, 4)), trigger))
        self.array = np.hstack((np.zeros((self.length_array, 4)), self.pattern_trigger, np.zeros((self.length_array, 4))))

        self.point_x_period = int(self.scan_rate / 996.31 / 2)
        self.points_x_cycle = int(self.cycle_duration * self.scan_rate)

        self.numb_periods_x_cycle = int(self.points_x_cycle / self.point_x_period)

    def change_frequency(self, frequency):
        self.frequency = frequency
        new_length_array = int(self.scan_rate * self.numb_cycles / self.frequency)

        if new_length_array > self.length_array:
            self.array = np.vstack((self.array, np.zeros((new_length_array - self.length_array, 16))))
            self.length_array = new_length_array
        else:
            self.array = self.array[:new_length_array, :]
            self.length_array = new_length_array

    def change_numb_cycles(self, numb_cycles):
        self.numb_cycles = numb_cycles
        new_length_array = int(self.scan_rate * self.numb_cycles / self.frequency)

        if new_length_array > self.length_array:
            self.array = np.vstack((self.array, np.zeros((new_length_array - self.length_array, 16))))
            self.length_array = new_length_array
        else:
            self.array = self.array[:new_length_array, :]
            self.length_array = new_length_array

    def change_cycle_duration(self, cycle_duration):
        self.cycle_duration = 0.001 * cycle_duration
        self.points_x_cycle = int(self.cycle_duration * self.scan_rate)
        self.numb_periods_x_cycle = int(self.points_x_cycle / self.point_x_period)

    def define_array_to_send(self, blue_duty_cycle):
        if self.array.shape[1] == 16:
            self.array = self.array[:, :-4]
        blue_dc = 0.01 * blue_duty_cycle

        high_points = int(self.point_x_period * blue_dc)
        low_points = int(self.point_x_period - high_points)
        period = np.vstack((np.zeros((low_points, 1)), np.ones((high_points, 1))))
        enable_blue_x_single_cycle = np.tile(period, (self.numb_periods_x_cycle, 4))
        if len(enable_blue_x_single_cycle) < self.points_x_cycle:
            enable_blue_x_single_cycle = np.vstack((enable_blue_x_single_cycle, np.zeros((self.points_x_cycle - len(enable_blue_x_single_cycle), 4))))

        check_points_to_add = int(self.scan_rate / self.frequency)
        if len(enable_blue_x_single_cycle) < check_points_to_add:
            enable_blue_x_single_period = np.vstack((enable_blue_x_single_cycle, np.zeros((check_points_to_add - len(enable_blue_x_single_cycle), 4))))
        else:
            enable_blue_x_single_period = enable_blue_x_single_cycle[:check_points_to_add, :]

        enable_blue = np.tile(enable_blue_x_single_period, (self.numb_cycles, 1))

        self.array = np.hstack((self.array, enable_blue))
        array_to_send = np.sum(self.array * (2 ** np.arange(0, self.array.shape[1], 1)), axis=1).astype(np.uint32)

        return array_to_send, self.scan_rate


if __name__ == '__main__':
    """seq = SequenciatorThreshold(2, 10, 4)
    array = seq.define_array_to_send(50)"""
    scan_rate = 10000000
    scan_time = 1 / scan_rate

    time_pre_ill = 200
    time_pre_stim = 200
    time_stim = 3000
    time_post_stim = 200

    start_frequency = 5
    pre_cond = 2
    final_frequency = 10
    step = 2
    if final_frequency > start_frequency:
        sn_values = np.arange(start_frequency, final_frequency + 1, step)
    else:
        sn_values = np.arange(start_frequency, final_frequency - 1, -step)
    time_el_stim = 1 / sn_values[0] * pre_cond
    for value in sn_values[1:]:
        time_el_stim += 1 / value
    if time_el_stim * 1000 > time_stim:
        print("NO!")

    dict = {'S1S2': [sn_values, pre_cond]}
    sequenciator = Sequenciator(scan_rate, 5, 50, dict)

    sequenciator.define_pre_ill_array(time_pre_ill)
    sequenciator.define_pre_stim_array(time_pre_stim)
    sequenciator.define_stim_array(time_stim)
    sequenciator.define_post_stim_array(time_post_stim)

    array_to_send, _ = sequenciator.define_array_to_send()

    master_task = nidaqmx.Task()
    master_task.do_channels.add_do_chan("Dev2/port0/line0:31", line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
    master_task.timing.cfg_samp_clk_timing(rate=scan_rate, sample_mode=AcquisitionType.FINITE, samps_per_chan=array_to_send.size)
    number_of_samples_written = master_task.write(array_to_send)

    master_task.start()
    master_task.wait_until_done(timeout=scan_time * array_to_send.size + 1)
    master_task.stop()

    point_interval = point_interval * 1000
    time_pre_ill = time_pre_ill * 1000
    time_pre_stim = time_pre_stim * 1000
    time_stim = time_stim * 1000
    time_post_stim = time_post_stim * 1000

    total_time = time_pre_ill + time_pre_stim + time_stim + time_post_stim

    v_total_time = np.arange(0, total_time, point_interval)
    v_total_time = v_total_time[:len(v_total_time) - 1]

    plt.figure(figsize=(10, 10))
    plt.subplot(4, 1, 1)
    plt.step(v_total_time, array[0, :], linewidth=2, where='post')
    plt.axvline(x=time_pre_ill, color='r', linestyle='--')
    plt.axvline(x=time_pre_ill + time_pre_stim, color='r', linestyle='--')
    plt.axvline(x=time_pre_ill + time_pre_stim + time_stim, color='r', linestyle='--')
    plt.axvline(x=time_pre_ill + time_pre_stim + time_stim + time_post_stim, color='r', linestyle='--')
    plt.ylim(-0.5, 1.5)
    plt.ylabel('Trig Cam 1')
    plt.grid(True)

    plt.subplot(4, 1, 2)
    plt.step(v_total_time, array[4, :], linewidth=2, where='post')
    plt.axvline(x=time_pre_ill, color='r', linestyle='--')
    plt.axvline(x=time_pre_ill + time_pre_stim, color='r', linestyle='--')
    plt.axvline(x=time_pre_ill + time_pre_stim + time_stim, color='r', linestyle='--')
    plt.axvline(x=time_pre_ill + time_pre_stim + time_stim + time_post_stim, color='r', linestyle='--')
    plt.ylim(-0.5, 1.5)
    plt.ylabel('Trig Pattern DMD 1')
    plt.grid(True)

    plt.subplot(4, 1, 3)
    plt.step(v_total_time, array[8, :], linewidth=2, where='post')
    plt.axvline(x=time_pre_ill, color='r', linestyle='--')
    plt.axvline(x=time_pre_ill + time_pre_stim, color='r', linestyle='--')
    plt.axvline(x=time_pre_ill + time_pre_stim + time_stim, color='r', linestyle='--')
    plt.axvline(x=time_pre_ill + time_pre_stim + time_stim + time_post_stim, color='r', linestyle='--')
    plt.ylim(-0.5, 1.5)
    plt.ylabel('En Red LED DMD 1')
    plt.grid(True)

    plt.subplot(4, 1, 4)
    plt.step(v_total_time, array[12, :], linewidth=2, where='post')
    plt.axvline(x=time_pre_ill, color='r', linestyle='--')
    plt.axvline(x=time_pre_ill + time_pre_stim, color='r', linestyle='--')
    plt.axvline(x=time_pre_ill + time_pre_stim + time_stim, color='r', linestyle='--')
    plt.axvline(x=time_pre_ill + time_pre_stim + time_stim + time_post_stim, color='r', linestyle='--')
    plt.ylim(-0.5, 1.5)
    plt.ylabel('En Blue LED DMD 1')
    plt.grid(True)

    plt.suptitle('Tutte le Fasi')
    plt.show()

    sequenciator_junior = SequenciatorJunior(50, 50, 5, 50, 5, 50, 5, 50)
    sequenciator_junior.enable_dmd1(False, True)
    sequenciator_junior.enable_dmd2(False, True)
    sequenciator_junior.enable_dmd3(True, False)
    sequenciator_junior.enable_dmd4(False, True)

    array_to_send = sequenciator_junior.define_array_to_send()

    #plot array
    """time = np.arange(0, array.shape[1], 1)
    plt.figure(figsize=(10, 10))
    plt.subplot(4, 1, 1)
    plt.step(time, array[4, :], linewidth=2, where='post')
    plt.ylim(-0.5, 1.5)
    plt.ylabel('Trig DMD 1')
    plt.grid(True)
    plt.show()"""

    time = 1/1000000
    master_task = nidaqmx.Task()
    master_task.do_channels.add_do_chan("Dev2/port0/line0:31", line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
    master_task.timing.cfg_samp_clk_timing(rate=1000000, sample_mode=AcquisitionType.FINITE,
                                           samps_per_chan=array_to_send.size)
    number_of_samples_written = master_task.write(array_to_send)

    master_task.start()
    master_task.wait_until_done(timeout=time * array_to_send.size + 1)
    master_task.stop()