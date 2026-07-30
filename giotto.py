"""Render device-state overlays on the platform-status illustration."""

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QPainter


class Giotto:
    """Maintain and draw the visual state of cameras and DMDs."""
    def __init__(self, image_on, image_off):
        self.image_on = image_on
        self.image_off = image_off

        self.platform_regions = [
            (0, 30, 210, 150), # CAM 4 idx 0
            (210, 110, 40, 60), # CAM 4 idx 1
            (210, 0, 100, 95), # DMD 3 idx 2
            (250, 80, 50, 110), # DMD 3 idx 3
            (300, 40, 290, 110), # CAM 3 idx 4
            (300, 120, 50, 50), # CAM 3 idx 5
            (0, 180, 250, 50), # DMD 4 idx 6
            (300, 170, 250, 50), # DMD 2 idx 7
            (0, 230, 230, 180), # CAM 1 idx 8
            (230, 230, 20, 40), # CAM 1 idx 9
            (250, 210, 50, 90), # DMD 1 idx 10
            (230, 300, 80, 90), # DMD 1 idx 11
            (300, 220, 240, 130), # CAM 2 idx 12
            (300, 220, 20, 20), # CAM 2 idx 13
        ]
        self.platform_states = [False] * len(self.platform_regions)
        self.sequences_sent = False

    def draw(self, device_idx, current_image, forced=False, dmd=None):
        if forced:
            if dmd == 1:
                for i in  [10, 11]:
                    self.platform_states[i] = False
            elif dmd == 2:
                self.platform_states[7] = False
            elif dmd == 3:
                for i in [2, 3]:
                    self.platform_states[i] = False
            elif dmd == 4:
                self.platform_states[6] = False
        else:
            self.platform_states[device_idx] = not self.platform_states[device_idx]

        x, y, w, h = self.platform_regions[device_idx]

        painter = QPainter(current_image)
        if self.platform_states[device_idx]:
            cropper_on = self.image_on.copy(x, y, w, h)
            painter.drawPixmap(x, y, cropper_on)
        else:
            cropper_off = self.image_off.copy(x, y, w, h)
            painter.drawPixmap(x, y, cropper_off)
        painter.end()


        return current_image


if __name__ == '__main__':
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QGridLayout, QApplication
    import sys
    from PyQt6.QtGui import QPixmap
    from PyQt6.QtCore import Qt


    class DeviceStatusApp(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Device Configuration")

            # Layout principale
            self.layout = QVBoxLayout()

            label_size = QSize(550, 400)

            # Caricamento delle immagini principali
            self.image_off = QPixmap("Icons/platform_not_configured.png").scaled(label_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)  # Immagine con dispositivi spenti
            self.image_on = QPixmap("icons/platform_configured.png").scaled(label_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)  # Immagine con dispositivi accesi

            self.gi8 = Giotto(self.image_on, self.image_off)

            # Stato iniziale dei dispositivi
            self.device_states = [False] * 6  # False = spento, True = acceso

            # QLabel per visualizzare l'immagine generale
            self.image_label = QLabel(self)
            self.image_label.setFixedSize(label_size)
            self.current_image = self.image_off.copy()  # Copia dell'immagine per modifica dinamica
            self.image_label.setPixmap(self.current_image)
            self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(self.image_label)

            # Pulsanti per attivare/disattivare dispositivi
            self.button_layout = QGridLayout()
            button_cam4 = QPushButton(f"Toggle CAM 4")
            button_cam4.clicked.connect(lambda checked: self.toggle_device([0, 1]))
            button_dmd3 = QPushButton(f"Toggle DMD 3")
            button_dmd3.clicked.connect(lambda checked: self.toggle_device([2, 3]))
            button_cam3 = QPushButton(f"Toggle CAM 3")
            button_cam3.clicked.connect(lambda checked: self.toggle_device([4, 5]))
            button_dmd4 = QPushButton(f"Toggle DMD 4")
            button_dmd4.clicked.connect(lambda checked: self.toggle_device([6]))
            button_dmd2 = QPushButton(f"Toggle DMD 2")
            button_dmd2.clicked.connect(lambda checked: self.toggle_device([7]))
            button_cam1 = QPushButton(f"Toggle CAM 1")
            button_cam1.clicked.connect(lambda checked: self.toggle_device([8, 9]))
            button_dmd1 = QPushButton(f"Toggle DMD 1")
            button_dmd1.clicked.connect(lambda checked: self.toggle_device([10, 11]))
            button_cam2 = QPushButton(f"Toggle CAM 2")
            button_cam2.clicked.connect(lambda checked: self.toggle_device([12, 13]))

            titolo = QPushButton("Title")
            titolo.clicked.connect(lambda checked: self.toggle_device([14]))

            self.button_layout.addWidget(button_cam4, 0, 0)
            self.button_layout.addWidget(button_dmd3, 0, 1)
            self.button_layout.addWidget(button_cam3, 0, 2)
            self.button_layout.addWidget(button_dmd4, 0, 3)
            self.button_layout.addWidget(button_dmd2, 1, 0)
            self.button_layout.addWidget(button_cam1, 1, 1)
            self.button_layout.addWidget(button_dmd1, 1, 2)
            self.button_layout.addWidget(button_cam2, 1, 3)
            self.layout.addLayout(self.button_layout)
            self.layout.addWidget(titolo)
            self.setStyleSheet("""QWidget {background-color: white;}
            QPushButton {background-color: #f0f0f0; border: 1px solid #ccc; border-radius: 5px; padding: 5px 10px; 
            font-size: 14px; color: #333; font-weight: bold;}""")

            # Imposta il layout principale
            self.setLayout(self.layout)

        def toggle_device(self, device_idx):
            for idx in device_idx:
                self.current_image = self.gi8.draw(idx, self.current_image)

            self.image_label.setPixmap(self.current_image)


    app = QApplication(sys.argv)
    main_window = DeviceStatusApp()
    main_window.show()
    sys.exit(app.exec())
