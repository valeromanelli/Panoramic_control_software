"""
Base interface for camera-control implementations.

The `CameraBase` class defines the common operations expected from camera
drivers used by the acquisition platform, including initialization, exposure
control, acquisition, region-of-interest configuration, and device shutdown.

Concrete camera drivers should subclass `CameraBase` and override the methods
supported by the corresponding hardware.

This module contains code adapted from the UUTrack project.
See `THIRD_PARTY_NOTICES.md` for attribution and licensing information.
"""


class cameraBase():
    """Compatibility interface implemented by concrete camera backends."""
    MODE_CONTINUOUS = 1
    MODE_SINGLE_SHOT = 0

    def __init__(self, camera):
        self.camera = camera
        self.running = False
        self.maxWidth = 0
        self.maxHeight = 0
        self.exposure = 0

    def initializeCamera(self):
        """
        Initializes the camera.
        """
        self.maxWidth = self.GetCCDWidth()
        self.maxHeight = self.GetCCDHeight()
        return True

    def triggerCamera(self):
        """
        Triggers the camera.
        """
        print("Not Implemented")

    def setAcquisitionMode(self, mode):
        """
        Set the readout mode of the camera: Single or continuous.
        :param int mode: One of self.MODE_CONTINUOUS, self.MODE_SINGLE_SHOT
        :return:
        """
        self.mode = mode

    def getAcquisitionMode(self):
        """
        Returns the acquisition mode, either continuous or single shot.
        """
        return self.mode

    def acquisitionReady(self):
        """
        Checks if the acquisition in the camera is over.
        """
        print("Not Implemented")

    def setExposure(self, exposure):
        """
        Sets the exposure of the camera.
        """
        self.exposure = exposure
        print("Not Implemented")

    def getExposure(self):
        """
        Gets the exposure time of the camera.
        """
        print("Not Implemented")
        return self.exposure

    def readCamera(self):
        """
        Reads the camera
        """
        print("Not Implemented")

    def setROI(self, X, Y):
        """ Sets up the ROI. Not all cameras are 0-indexed, so this is an important
        place to define the proper ROI.

        :param array X: array type with the coordinates for the ROI X[0], X[1]
        :param array Y: array type with the coordinates for the ROI Y[0], Y[1]
        :return:
        """
        print("Not Implemented")

    def clearROI(self):
        """
        Clears the ROI from the camera.
        """
        self.setROI(self.maxWidth, self.maxHeight)

    def getSize(self):
        """Returns the size in pixels of the image being acquired. This is useful for checking the ROI settings.
        """
        print("Not Implemented")

    def getSerialNumber(self):
        """Returns the serial number of the camera.
        """
        print("Not Implemented")

    def GetCCDWidth(self):
        """
        Returns the CCD width in pixels
        """
        print("Not Implemented")

    def GetCCDHeight(self):
        """
        Returns: the CCD height in pixels
        """
        print("Not Implemented")

    def stopAcq(self):
        """Stops the acquisition without closing the connection to the camera."""
        print("Not Implemented")

    def stopCamera(self):
        """Stops the acquisition and closes the connection with the camera.
        """
        try:
            # Closing the camera
            print("Not Implemented")
        except:
            # Monitor failed to close
            print("Not Implemented")
