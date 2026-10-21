"""Central design-system stylesheet for FileForge.

All widgets should rely on these shared rules rather than one-off styling.
"""

APP_STYLESHEET = """
/* ---------- Design tokens (Qt StyleSheet approximations) ---------- */
QWidget {
    background-color: #F4F6F8;
    color: #1F2933;
    font-family: "Segoe UI", "Segoe UI Variable", sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #F4F6F8;
}

/* ---------- Sidebar ---------- */
#Sidebar {
    background-color: #1B2838;
    border: none;
    min-width: 220px;
    max-width: 260px;
}

#SidebarBrand {
    background-color: transparent;
    color: #F5F7FA;
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 0.4px;
    padding: 20px 18px 8px 18px;
}

#SidebarTagline {
    background-color: transparent;
    color: #9AA5B1;
    font-size: 11px;
    padding: 0 18px 16px 18px;
}

QListWidget#NavList {
    background-color: transparent;
    border: none;
    outline: none;
    padding: 4px 10px 16px 10px;
    color: #D9E2EC;
}

QListWidget#NavList::item {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 10px 12px;
    margin: 2px 0;
    color: #D9E2EC;
}

QListWidget#NavList::item:hover {
    background-color: #243447;
    color: #FFFFFF;
}

QListWidget#NavList::item:selected {
    background-color: #2F6FED;
    color: #FFFFFF;
    font-weight: 600;
}

QListWidget#NavList::item:focus {
    border: 2px solid #7EB6FF;
    padding: 8px 10px;
}

/* ---------- Content area ---------- */
#ContentHost {
    background-color: #F4F6F8;
}

#PageTitle {
    background-color: transparent;
    color: #102A43;
    font-size: 24px;
    font-weight: 700;
    padding: 0;
    margin: 0;
}

#PageSubtitle {
    background-color: transparent;
    color: #486581;
    font-size: 13px;
    padding: 0;
    margin: 0;
}

#SectionCard {
    background-color: #FFFFFF;
    border: 1px solid #D9E2EC;
    border-radius: 10px;
}

#MutedLabel {
    background-color: transparent;
    color: #627D98;
}

#BodyLabel {
    background-color: transparent;
    color: #243B53;
}

#BadgeLabel {
    background-color: #E0E7FF;
    color: #334E68;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 600;
}

/* ---------- Buttons ---------- */
QPushButton {
    background-color: #2F6FED;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 9px 16px;
    font-weight: 600;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #2662D9;
}

QPushButton:pressed {
    background-color: #1F54C0;
}

QPushButton:disabled {
    background-color: #BCCCDC;
    color: #829AB1;
}

QPushButton:focus {
    outline: none;
    border: 2px solid #102A43;
    padding: 7px 14px;
}

QPushButton#SecondaryButton {
    background-color: #FFFFFF;
    color: #243B53;
    border: 1px solid #9FB3C8;
}

QPushButton#SecondaryButton:hover {
    background-color: #F0F4F8;
}

QPushButton#SecondaryButton:disabled {
    background-color: #F0F4F8;
    color: #829AB1;
    border: 1px solid #D9E2EC;
}

/* ---------- Form controls ---------- */
QLineEdit, QComboBox, QPlainTextEdit {
    background-color: #FFFFFF;
    border: 1px solid #9FB3C8;
    border-radius: 8px;
    padding: 8px 10px;
    selection-background-color: #2F6FED;
    selection-color: #FFFFFF;
}

QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {
    border: 2px solid #2F6FED;
    padding: 7px 9px;
}

QLineEdit:disabled, QComboBox:disabled {
    background-color: #F0F4F8;
    color: #829AB1;
}

QCheckBox {
    background-color: transparent;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #9FB3C8;
    border-radius: 4px;
    background-color: #FFFFFF;
}

QCheckBox::indicator:checked {
    background-color: #2F6FED;
    border-color: #2F6FED;
}

QCheckBox:focus {
    color: #102A43;
}

/* ---------- Status / empty ---------- */
#StatusBar {
    background-color: #FFFFFF;
    color: #486581;
    border-top: 1px solid #D9E2EC;
}

#EmptyStateTitle {
    background-color: transparent;
    color: #243B53;
    font-size: 16px;
    font-weight: 600;
}

#EmptyStateBody {
    background-color: transparent;
    color: #627D98;
}
"""
