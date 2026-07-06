def style(widget):
    widget.setStyleSheet("""
                    QWidget {background-color: white;}          
                    QDoubleSpinBox {
                        border: 1px solid #ccc;
                        border-radius: 4px;
                        padding: 2px;
                    }
                    QDoubleSpinBox:focus {
                        border: 1px solid #0078d7;
                    }
                    
                    QGroupBox {
                        background-color: white;
                        border: 2px solid blue;
                        border-radius: 10px;
                        margin-top: 15px;
                        box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.2); 
                    }
                    QGroupBox:title {
                        subcontrol-origin: margin;
                        subcontrol-position: top center;
                        padding: 0 5px;
                        background-color: blue;
                        color: white;
                        font-weight: bold;
                        border-radius: 5px;
                    }
                    
                    QListWidget {
                        background-color: #F5F5F5; /* Colore di sfondo */
                        border: 1px solid #C0C0C0; /* Bordi */
                        border-radius: 5px; /* Angoli arrotondati */
                        font-size: 12px; /* Dimensione font */
                        padding: 5px; /* Padding interno */
                    }
                    QListWidget::item {
                        padding: 9px; /* Padding per gli elementi */
                        border-bottom: 1px solid #E0E0E0; /* Bordi tra gli elementi */
                        color: #333; /* Colore del testo */
                    }
                    QListWidget::item:selected {
                        background-color: #007BFF; /* Colore di sfondo quando selezionato */
                        color: white; /* Colore del testo quando selezionato */
                    }
                    QListWidget::item:hover {
                        background-color: #D3E6FF; /* Colore di sfondo al passaggio del mouse */
                    }
    
                    QPushButton {
                        background-color: #0078D4;
                        border: 2px solid blue;
                        border-radius: 10px;
                        background-color: #f0f0f0;
                        padding: 5px;
                    }
                    QPushButton:hover {
                        background-color: #e0e0e0;
                    }
                    QPushButton:pressed {
                        background-color: #d0d0d0;
                    }
                    
                    QScrollArea {
                        border: 2px solid #4682B4;
                        border-radius: 8px;
                        background-color: white;
                    }
                    QScrollArea QWidget {
                        background-color: transparent;
                    }               
                    QScrollBar:horizontal {
                        border: none;
                        background: #E0E0E0;  /* Sfondo leggero per la scrollbar */
                        width: 12px;  /* Larghezza della scrollbar verticale */
                        margin: 2px 0;
                        border-radius: 6px;
                    }                
                    QScrollBar::handle:vertical {
                        background: #888;  /* Colore principale della maniglia */
                        min-height: 20px;  /* Altezza minima per il handle */
                        border-radius: 6px;
                    }                
                    QScrollBar::handle:vertical:hover {
                        background: #555;  /* Colore quando il mouse è sopra la maniglia */
                    }               
                    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                        border: none;
                        background: none;
                        height: 0px;
                        width: 0px;
                        margin: 0;
                    }                
                    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                        background: none;
                    }                
                    QScrollBar:horizontal {
                        border: none;
                        background: #E0E0E0;  /* Sfondo leggero per la scrollbar */
                        height: 12px;  /* Altezza della scrollbar orizzontale */
                        margin: 0 2px;
                        border-radius: 6px;
                    }                
                    QScrollBar::handle:horizontal {
                        background: #888;  /* Colore principale della maniglia */
                        min-width: 20px;  /* Larghezza minima per il handle */
                        border-radius: 6px;
                    }               
                    QScrollBar::handle:horizontal:hover {
                        background: #555;  /* Colore quando il mouse è sopra la maniglia */
                    }                
                    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                        border: none;
                        background: none;
                        width: 0px;
                        height: 0px;
                        margin: 0;
                    }                
                    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                        background: none;
                    }
                    
                    QSpinBox {
                        border: 1px solid #ccc;
                        border-radius: 4px;
                        padding: 2px;
                    }
                    QSpinBox:focus {
                        border: 1px solid #0078d7;
                    }
                    
                    QToolButton {
                        border: 2px solid #A0A0A0; 
                        border-radius: 8px;  
                        background-color: transparent;  
                        padding: 4px;  
                        color: #404040;  
                        font-weight: bold;
                    }
                """)


def update_checkbox_style(check_box, dmd_selection=False):
    if dmd_selection:
        check_box.setStyleSheet("""
                    QCheckBox {
                        spacing: 8px; /* Distanza tra il box e il testo */
                        font-size: 12px;
                        font-family: Arial, Helvetica, sans-serif;
                        color: #333; /* Colore del testo */
                    }                   
                    QCheckBox::indicator {
                        width: 12px; /* Larghezza del box */
                        height: 12px; /* Altezza del box */
                        border: 2px solid #888; /* Bordo del box */
                        border-radius: 4px; /* Angoli arrotondati */
                        background-color: #f0f0f0; /* Colore di sfondo del box */
                    }                   
                    QCheckBox::indicator:hover {
                        border: 2px solid #555; /* Cambia il colore del bordo al passaggio del mouse */
                        background-color: #e8e8e8; /* Cambia il colore di sfondo */
                    }                   
                    QCheckBox::indicator:checked {
                        background-color: blue; /* Colore di sfondo quando selezionato */
                        border: 2px solid blue; /* Cambia il bordo quando selezionato */
                    }                   
                    QCheckBox::indicator:checked:hover {
                        background-color: blue; /* Sfondo più scuro quando selezionato e con hover */
                        border: 2px solid blue; /* Bordo più scuro quando selezionato e con hover */
                    }                   
                    QCheckBox::indicator:unchecked {
                        background-color: #f0f0f0; /* Sfondo quando non selezionato */
                        border: 2px solid #888; /* Bordo quando non selezionato */
                    }                   
                    QCheckBox::indicator:unchecked:hover {
                        border: 2px solid #555; /* Bordo quando non selezionato e con hover */
                        background-color: #e8e8e8; /* Sfondo quando non selezionato e con hover */
                    }
            """)
    else:
        check_box.setStyleSheet("""
                                QCheckBox {
                                    padding: 8px 15px;
                                    color: #444;
                                    background-color: #f9f9f9;
                                    border-radius: 8px;
                                    border: 1px solid #ccc;
                                    transition: background-color 0.3s, color 0.3s;
                                }
                                QCheckBox:hover {
                                    background-color: #e6e6e6;
                                    color: #000;
                                }
                                QCheckBox::indicator {
                                    width: 20px;
                                    height: 20px;
                                    border-radius: 10px;
                                    border: 2px solid #bbb;
                                    background-color: transparent;
                                    transition: background-color 0.3s, border 0.3s;
                                }
                                QCheckBox::indicator:checked {
                                    background-color: #0078D4;  
                                    border: 2px solid #0078D4;
                                }
                                QCheckBox::indicator:unchecked {
                                    background-color: transparent;
                                    border: 2px solid #bbb;
                                }
                                QCheckBox::indicator:hover {
                                    border: 2px solid #555;
                                }
                            """)



def update_groupbox_style(group_box, mode, label1=None, label2=None, label3=None, label4=None):
    if mode == 'subgroup':
        group_box.setStyleSheet("""
                            QGroupBox {
                                background-color: white;
                                border: 2px solid #4682B4;
                                border-radius: 10px;
                                margin-top: 15px;
                                box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.2); /* effetto ombra */
                            }

                            QGroupBox:title {
                                subcontrol-origin: margin;
                                subcontrol-position: top center;
                                padding: 0 5px;
                                background-color: #4682B4;
                                color: white;
                                font-weight: bold;
                                border-radius: 5px;
                            }
                        """)

    elif mode == 'checked':
        group_box.setStyleSheet("""
                            QGroupBox {
                                background-color: white;
                                border: 2px solid blue;
                                border-radius: 10px;
                                margin-top: 15px;
                                box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.2); 
                            }
                        """)
        label1.setStyleSheet("""
                            QLabel {
                                background-color: white;
                            }
                        """)
        if label2 is not None:
            label2.setStyleSheet("""
                            QLabel {
                                background-color: white;
                            }
                        """)
        if label3 is not None:
            label3.setStyleSheet("""
                            QLabel {
                                background-color: white;
                            }
                        """)

        if label4 is not None:
            label4.setStyleSheet("""
                            QLabel {
                                background-color: white;
                            }
                        """)

    elif mode == 'unchecked':
        group_box.setStyleSheet("""
                            QGroupBox {
                                background-color: #f0f0f0;
                                border: 2px solid gray;
                                border-radius: 10px;
                                margin-top: 15px;
                                box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.2); 
                            }
                        """)
        label1.setStyleSheet("""
                            QLabel {
                                background-color: #f0f0f0;
                            }
                        """)
        if label2 is not None:
            label2.setStyleSheet("""
                            QLabel {
                                background-color: #f0f0f0;
                            }
                        """)
        if label3 is not None:
            label3.setStyleSheet("""
                            QLabel {
                                background-color: #f0f0f0;
                            }
                        """)

        if label4 is not None:
            label4.setStyleSheet("""
                            QLabel {
                                background-color: #f0f0f0;
                            }
                        """)


def update_toolbutton_style(tool_button, mode, clickable=False):
    if clickable:
        tool_button.setStyleSheet("""
                        QToolButton {
                            background-color: #f0f0f0; /* Sfondo base */
                            border: 2px solid #d0d0d0; /* Bordo sottile */
                            border-radius: 8px; /* Angoli arrotondati */
                            padding: 6px;
                            color: #333333; /* Colore del testo */
                            font: bold 14px "Arial";
                            text-align: center;
                            margin: 5px; /* Margine esterno */
                        }
                        QToolButton:hover {
                            background-color: #e6f7ff; /* Colore di sfondo al passaggio del mouse */
                            border: 2px solid #80bfff; /* Bordo evidenziato */
                        }
                        QToolButton:pressed {
                            background-color: #cceeff; /* Colore di sfondo quando premuto */
                            border: 2px solid #3399ff; /* Bordo quando premuto */
                        }                      
                        QToolButton:disabled {
                            background-color: #f9f9f9; /* Sfondo quando disabilitato */
                            color: #a0a0a0; /* Testo disabilitato */
                            border: 2px solid #e0e0e0; /* Bordo disabilitato */
                        }                       
                        QToolButton::menu-indicator {
                            image: none; /* Rimuove l'indicatore del menu */
                        }                       
                        QToolButton QLabel {
                            margin: 8px 0 0 0; /* Margine tra l'immagine e il testo */
                            text-align: center; /* Centrare il testo */
                        }
                """)
    else:
        if mode == 'on':
            tool_button.setStyleSheet("""
                            QToolButton {
                                border: 2px solid green;
                                border-radius: 10px; 
                                background-color: #ccffcc; 
                                padding: 4px;
                                color: green;
                                font-weight: bold;
                            }
                        """)

        elif mode == 'off':
            tool_button.setStyleSheet("""
                        QToolButton {
                            border: 2px solid red;
                            border-radius: 10px; 
                            background-color: #ffcccc; 
                            padding: 4px;
                            color: red;
                            font-weight: bold;
                        }
                    """)


def update_lineedit_style(line_edit):
    line_edit.setStyleSheet("""
                    QLineEdit {
                        padding: 4px 8px; 
                        border: 1px solid #ccc; 
                        border-radius: 5px; 
                        background-color: #f9f9f9;
                        font-size: 14px; 
                        color: #333;
                    }
                    QLineEdit:hover {
                        border: 1px solid #a6a6a6;
                    }
                    QLineEdit:focus {
                        border: 1px solid #0078D4;  /* Colore di focus (blu) */
                        background-color: #ffffff;
                    }
                """)