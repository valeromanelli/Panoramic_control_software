"""
    UUTrack.Model.Cameras.Hamamatsu.py
    ==================================

    Model class for controlling Hamamatsu cameras via de DCAM-API. At the time of writing this class,
    little documentation on the DCAM-API was available. Hamamatsu has a different time schedule regardin support of
    their own API. However, Zhuang's lab Github repository had a python driver for the Orca camera and with a bit of
    tinkering things worked out.

    DCAM-API relies mostly on setting parameters into the camera. The correct data type of each parameter is not well
    documented; however it is possible to print all the available properties and work from there. The properties are
    stored in a filed named params.txt next to the :mod:`Hamamatsu Driver
    <UUTrack.Controller.devices.hamamatsu.hamamatsu_camera>`

    .. note:: When setting the ROI, Hamamatsu only allows to set multiples of 4 for every setting (X,Y and vsize,
        hsize). This is checked in the function. Changing the ROI cannot be done directly, one first needs to disable it
        and then re-enable.


    .. sectionauthor:: Aquiles Carattino <aquiles@aquicarattino.com>
"""
import cv2
import numpy as np
from camere_basic_controls import HamamatsuCamera
from skeleton import cameraBase


class camera(cameraBase):
    """High-level Hamamatsu camera adapter used by the application."""
    MODE_CONTINUOUS = 1
    MODE_SINGLE_SHOT = 0
    MODE_PANORAMIC = 2

    def __init__(self,camera):
        self.cam_id = camera # Monitor ID
        self.camera = HamamatsuCamera(camera)
        self.running = False
        self.mode = self.MODE_CONTINUOUS

    def initializeCamera(self):
        """ Initializes the camera.

        :return:
        """

        self.camera.initCamera()
        self.maxWidth = self.GetCCDWidth()
        self.maxHeight = self.GetCCDHeight()
        #This is important to not have shufled patches of the CCD.
        #Have to check documentation!!
        self.camera.setPropertyValue("sensor_mode", 1)
        self.camera.setPropertyValue("image_pixel_type", 2)
        self.camera.setPropertyValue("binning", 1)
        self.camera.setPropertyValue("readout_speed", 2)
        self.camera.setPropertyValue("defect_correct_mode", 2)
        self.camera.setPropertyValue('trigger_source', 1)
        self.camera.setPropertyValue('trigger_mode', 1)
        self.camera.setPropertyValue('trigger_active', 1)
        self.camera.setPropertyValue("trigger_polarity", 1)

    def getSensorMode(self):
        """
        Returns the sensor mode of the camera.
        """
        return self.camera.getPropertyValue("sensor_mode")

    def setSensorMode(self, mode):
        """
        Sets the sensor mode of the camera.
        """
        self.camera.setPropertyValue("sensor_mode", mode)
        return self.getSensorMode()

    def getPixelType(self):
        """
        Returns the pixel type of the camera.
        """
        return self.camera.getPropertyValue("image_pixel_type")

    def setPixelType(self, pixel_type):
        """
        Sets the pixel type of the camera.
        """
        self.camera.setPropertyValue("image_pixel_type", pixel_type)
        return self.getPixelType()

    def getRedoutSpeed(self):
        """
        Returns the readout speed of the camera.
        """
        return self.camera.getPropertyValue("readout_speed")

    def setReadoutSpeed(self, speed):
        """
        Sets the readout speed of the camera.
        """
        self.camera.setPropertyValue("readout_speed", speed)
        return self.getRedoutSpeed()

    def getBinning(self):
        """
        Returns the binning of the camera.
        """
        return self.camera.getPropertyValue("binning")

    def setBinning(self, binning):
        """
        Sets the binning of the camera.
        """
        self.camera.setPropertyValue("binning", binning)
        return self.getBinning()

    def getTrigSource(self):
        """
        Returns the trigger source of the camera.
        """
        return self.camera.getPropertyValue("trigger_source")

    def setTrigSource(self, source):
        """
        Sets the trigger source of the camera.
        """
        self.camera.setPropertyValue("trigger_source", source)
        return self.getTrigSource()

    def getTrigMode(self):
        """
        Returns the trigger mode of the camera.
        """
        return self.camera.getPropertyValue("trigger_mode")

    def setTrigMode(self, mode):
        """
        Sets the trigger mode of the camera.
        """
        self.camera.setPropertyValue("trigger_mode", mode)
        return self.getTrigMode()

    def getTrigActive(self):
        """
        Returns the trigger active of the camera.
        """
        return self.camera.getPropertyValue("trigger_active")

    def setTrigActive(self, active):
        """
        Sets the trigger active of the camera.
        """
        self.camera.setPropertyValue("trigger_active", active)
        return self.getTrigActive()

    def getTrigPolarity(self):
        """
        Returns the trigger polarity of the camera.
        """
        return self.camera.getPropertyValue("trigger_polarity")

    def setTrigPolarity(self, polarity):
        """
        Sets the trigger polarity of the camera.
        """
        self.camera.setPropertyValue("trigger_polarity", polarity)
        return self.getTrigPolarity()

    def getFrameBundleMode(self):
        """
        Returns the frame bundle mode of the camera.
        """
        return self.camera.getPropertyValue("framebundle_mode")

    def setFrameBundleMode(self, mode):
        """
        Sets the frame bundle mode of the camera.
        """
        self.camera.setPropertyValue("framebundle_mode", mode)
        return self.getFrameBundleMode()

    def getFrameBundleNumber(self):
        """
        Returns the frame bundle number of the camera.
        """
        return self.camera.getPropertyValue("framebundle_number")

    def setFrameBundleNumber(self, number):
        """
        Sets the frame bundle number of the camera.
        """
        self.camera.setPropertyValue("framebundle_number", number)
        return self.getFrameBundleNumber()

    def getFrames(self):
        """
        Returns the frames of the camera.
        """
        return self.camera.getFrames()

    def triggerCamera(self, mode=1, stop_condition=0):
        """Triggers the camera.
        """
        if mode == self.MODE_CONTINUOUS:
            self.camera.startAcquisition()
        elif mode == self.MODE_SINGLE_SHOT:
            self.camera.startAcquisition()
            self.camera.stopAcquisition()
        elif mode == self.MODE_PANORAMIC:
            self.camera.startAcquisitionExternal(stop_condition)

    def setAcquisitionMode(self, mode):
        """
        Set the readout mode of the camera: Single or continuous.
        Parameters
        mode : int
        One of self.MODE_CONTINUOUS, self.MODE_SINGLE_SHOT
        """
        self.mode = mode
        if mode == self.MODE_CONTINUOUS:
            #self.camera.setPropertyValue("trigger_source", 1)
            self.camera.settrigger(1)
            self.camera.setmode(self.camera.CAPTUREMODE_SEQUENCE)
        elif mode == self.MODE_SINGLE_SHOT:
            #self.camera.setPropertyValue("trigger_source", 3)
            self.camera.settrigger(1)
            self.camera.setmode(self.camera.CAPTUREMODE_SNAP)
        return self.getAcquisitionMode()

    def getAcquisitionMode(self):
        """Returns the acquisition mode, either continuous or single shot.
        """
        return self.mode

    def getPropRange(self, property):
        """
        Returns the range of values for a given property.
        """
        return self.camera.getPropertyRange(property)

    def acquisitionReady(self):
        """Checks if the acquisition in the camera is over.
        """
        return True

    def setExposure(self,exposure):
        """
        Sets the exposure of the camera.
        """
        self.camera.setPropertyValue("exposure_time", exposure)
        return self.camera.getPropertyValue("exposure_time")[0]

    def getExposure(self):
        """
        Gets the exposure time of the camera.
        """
        return self.camera.getPropertyValue("exposure_time")[0]

    def getReadout(self):
        """
        Gets the readout speed of the camera.
        """
        return self.camera.getPropertyValue("timing_readout_time")[0]

    def getFrameRate(self):
        """
        Gets the frame rate of the camera.
        """
        return self.camera.getPropertyValue("internal_frame_rate")[0]

    def getFrameInterval(self):
        """
        Gets the frame interval of the camera.
        """
        return self.camera.getPropertyValue("internal_frame_interval")[0]

    def readCamera(self):
        """
        Reads the camera
        """
        [frames, dims] = self.camera.getFrames()
        img = []
        for f in frames:
            d = f.getData()
            d = np.reshape(d, (dims[1], dims[0]))
            d = d.T
            img.append(d)
        img = frames[-1].getData()
        img = np.reshape(img,(dims[0],dims[1]))
        img = cv2.flip(img, 1)
        return img

    def acquireData(self):
        """
        Reads the camera
        """
        [frames, dims] = self.camera.getFrames()
        img = []
        n = 0
        for f in frames:
            d = f.getData()
            d = np.reshape(d, (dims[1], dims[0]))
            d = d.T
            img.append(d)
            n += 1
        return img, n

    def disableSubarrayMode(self):
        """
        Disables the subarray mode of the camera.
        """
        self.camera.setPropertyValue("subarray_mode", 1)

    def ableROI(self, x, y):
        """
        Sets up the ROI. Not all cameras are 0-indexed, so this is an important
        place to define the proper ROI.
        X -- array type with the coordinates for the ROI X[0], X[1]
        Y -- array type with the coordinates for the ROI Y[0], Y[1]
        """
        h_pos = int(1024 - x / 2)
        v_pos = int(1024 - y / 2)

        # First needs to go full frame, if not, throws an error of subframe not valid
        self.camera.setPropertyValue("subarray_vpos", 0)
        self.camera.setPropertyValue("subarray_hpos", 0)
        self.camera.setPropertyValue("subarray_vsize", self.camera.max_height)
        self.camera.setPropertyValue("subarray_hsize", self.camera.max_width)
        self.camera.setSubArrayMode()

        #ROI 192x192: 928
        #ROI 128x128: 960
        #ROI 256x256: 896
        self.camera.setPropertyValue("subarray_vpos", v_pos)
        self.camera.setPropertyValue("subarray_hpos", h_pos)
        self.camera.setPropertyValue("subarray_vsize", y)
        self.camera.setPropertyValue("subarray_hsize", x)
        self.camera.setSubArrayMode()
        return self.getSize()

    def disableROI(self):
        """
        Sets up the ROI. Not all cameras are 0-indexed, so this is an important
        place to define the proper ROI.
        X -- array type with the coordinates for the ROI X[0], X[1]
        Y -- array type with the coordinates for the ROI Y[0], Y[1]
        """
        # First needs to go full frame, if not, throws an error of subframe not valid
        self.camera.setPropertyValue("subarray_vpos", 0)
        self.camera.setPropertyValue("subarray_hpos", 0)
        self.camera.setPropertyValue("subarray_vsize", self.camera.max_height)
        self.camera.setPropertyValue("subarray_hsize", self.camera.max_width)
        self.camera.setSubArrayMode()

        return self.getSize()

    def getSize(self):
        """Returns the size in pixels of the image being acquired. This is useful for checking the ROI settings.
        """
        X = self.camera.getPropertyValue("subarray_hsize")
        Y = self.camera.getPropertyValue("subarray_vsize")
        return X[0], Y[0]

    def getSerialNumber(self):
        """Returns the serial number of the camera.
        """
        return self.camera.getModelInfo(self.cam_id)

    def GetCCDWidth(self):
        """
        Returns
        The CCD width in pixels

        """
        return self.camera.max_width

    def GetCCDHeight(self):
        """
        Returns
        The CCD height in pixels

        """
        return self.camera.max_height

    def stopAcq(self):
        return self.camera.stopAcquisition()

    def stopCamera(self):
        """Stops the acquisition and closes the connection with the camera.
        """
        try:
            #Closing the camera
            self.camera.stopAcquisition()
            self.camera.shutdown()
            return True
        except:
            #Monitor failed to close
            return False
