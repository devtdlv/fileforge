"""Central design-system stylesheet for Junction.

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
    padding: 22px 18px 6px 18px;
}

#SidebarTagline {
    background-color: transparent;
    color: #9AA5B1;
    font-size: 11px;
    padding: 0 18px 18px 18px;
}

QListWidget#NavList {
    background-color: transparent;
    border: none;
    outline: none;
    padding: 4px 12px 18px 12px;
    color: #D9E2EC;
}

QListWidget#NavList::item {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 11px 12px;
    margin: 3px 0;
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
    border: 1px solid #5B8DEF;
}

QListWidget#NavList::item:focus {
    border: 2px solid #7EB6FF;
    padding: 10px 11px;
}

QListWidget#NavList::item:selected:focus {
    border: 2px solid #B6D4FE;
    padding: 10px 11px;
}

/* ---------- Content area ---------- */
#ContentHost {
    background-color: #F4F6F8;
}

#PageTitle {
    background-color: transparent;
    color: #102A43;
    font-size: 26px;
    font-weight: 700;
    padding: 0;
    margin: 0;
}

#PageSubtitle {
    background-color: transparent;
    color: #486581;
    font-size: 14px;
    line-height: 1.45;
    padding: 0 0 4px 0;
    margin: 0;
}

#SectionCard {
    background-color: #FFFFFF;
    border: 1px solid #D9E2EC;
    border-radius: 10px;
}

#HeroCard {
    background-color: #FFFFFF;
    border: 1px solid #D9E2EC;
    border-left: 4px solid #2F6FED;
    border-radius: 10px;
}

#SectionKicker {
    background-color: transparent;
    color: #2F6FED;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.6px;
    text-transform: uppercase;
}

#HeroTitle {
    background-color: transparent;
    color: #102A43;
    font-size: 18px;
    font-weight: 700;
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

QPushButton#PrimaryButton {
    padding: 11px 20px;
    font-size: 14px;
    min-height: 22px;
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

QPushButton#PrimaryButton:focus {
    padding: 9px 18px;
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
QLineEdit, QComboBox, QPlainTextEdit, QSpinBox {
    background-color: #FFFFFF;
    border: 1px solid #9FB3C8;
    border-radius: 8px;
    padding: 8px 10px;
    min-height: 18px;
    selection-background-color: #2F6FED;
    selection-color: #FFFFFF;
}

QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QSpinBox:focus {
    border: 2px solid #2F6FED;
    padding: 7px 9px;
}

QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
    background-color: #F0F4F8;
    color: #829AB1;
}

QGroupBox {
    background-color: #FFFFFF;
    border: 1px solid #D9E2EC;
    border-radius: 10px;
    margin-top: 12px;
    padding-top: 8px;
    font-weight: 600;
    color: #243B53;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #243B53;
}

QSplitter::handle {
    background-color: #D9E2EC;
}

QSplitter::handle:horizontal {
    width: 4px;
}

QSplitter::handle:vertical {
    height: 4px;
}

QSplitter::handle:hover {
    background-color: #9FB3C8;
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

/* ---------- Tables / progress ---------- */
QTableView {
    background-color: #FFFFFF;
    alternate-background-color: #F8FAFC;
    border: 1px solid #D9E2EC;
    border-radius: 8px;
    gridline-color: #E4E7EB;
    selection-background-color: #D6E4FF;
    selection-color: #102A43;
}

QHeaderView::section {
    background-color: #F0F4F8;
    color: #243B53;
    padding: 8px 10px;
    border: none;
    border-right: 1px solid #D9E2EC;
    border-bottom: 1px solid #D9E2EC;
    font-weight: 600;
    min-height: 28px;
}

QTableView::item {
    padding: 4px 8px;
}

/* Status emphasis helpers (foreground only; never rely on color alone) */
#StatusSuccess {
    color: #0F7B3A;
    font-weight: 600;
}

#StatusWarning {
    color: #B54708;
    font-weight: 600;
}

#StatusError {
    color: #B42318;
    font-weight: 600;
}

#StatValue {
    background-color: transparent;
    color: #102A43;
    font-size: 22px;
    font-weight: 700;
}

#StatCaption {
    background-color: transparent;
    color: #627D98;
    font-size: 12px;
}

#ShortcutCard {
    background-color: #FFFFFF;
    border: 1px solid #D9E2EC;
    border-radius: 10px;
}

#ShortcutCard:hover {
    border: 1px solid #2F6FED;
}

QProgressBar {
    background-color: #E4E7EB;
    border: none;
    border-radius: 6px;
    min-height: 8px;
    max-height: 8px;
}

QProgressBar::chunk {
    background-color: #2F6FED;
    border-radius: 6px;
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
