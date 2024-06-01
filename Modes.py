from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, QPushButton, \
    QGroupBox, QRadioButton, QVBoxLayout, QLineEdit, QLabel, QDateEdit, QListWidget, QFileDialog, QCheckBox, QButtonGroup, QDialog, QComboBox, QMessageBox, QGridLayout, QStackedWidget, QSpinBox
from PyQt5.QtGui import QDoubleValidator, QFont, QIcon
from PyQt5.QtCore import Qt, QDate

from support_classes import InputDialog
from DataManager import DataManager


class ModeWidget(QWidget):
    def __init__(self, figure_manager):
        super().__init__()
        self.figure_manager = figure_manager
        self.data_manager = DataManager()
        self.layout = QVBoxLayout(self)
        self.init_ui()

    def init_ui(self):
        pass


class ViewModeWidget(ModeWidget):
    def init_ui(self):
        self.dialog = InputDialog()

        # Creating grid layout to organize the checkboxes
        view_grid = QGridLayout()

        # Headings for Dot and X settings
        font = QFont()
        font.setBold(True)
        dot_heading = QLabel("Dot")
        dot_heading.setFont(font)
        x_heading = QLabel("X")
        x_heading.setFont(font)
        grid_heading = QLabel("\nGrid")
        grid_heading.setFont(font)
        other_heading = QLabel("\nOther")
        other_heading.setFont(font)

        # Placing the headings
        view_grid.addWidget(dot_heading, 0, 0)
        view_grid.addWidget(x_heading, 0, 1)
        view_grid.addWidget(grid_heading, 6, 0)
        view_grid.addWidget(other_heading, 6, 1)

        # Checkboxes for various view options
        self.dots_check = QCheckBox('Point')
        self.xs_check = QCheckBox('Point')
        self.dot_trends_check = QCheckBox('Trend')
        self.x_trends_check = QCheckBox('Trend')
        self.dot_lines_check = QCheckBox('Line')
        self.x_lines_check = QCheckBox('Line')
        self.dot_color_check = QCheckBox('Green')
        self.x_color_check = QCheckBox('Red')
        self.minor_grid_check = QCheckBox('Minor')
        self.major_grid_check = QCheckBox('Major')
        self.timing_floor_check = QCheckBox('Floor')
        self.timing_grid_check = QCheckBox('Timing')
        self.phase_lines_check = QCheckBox('Phase')
        self.aims_check = QCheckBox('Aim')

        # Adding checkboxes to the grid
        view_grid.addWidget(self.dots_check, 1, 0)
        view_grid.addWidget(self.dot_trends_check, 4, 0)
        view_grid.addWidget(self.dot_lines_check, 2, 0)
        view_grid.addWidget(self.dot_color_check, 3, 0)
        view_grid.addWidget(self.xs_check, 1, 1)
        view_grid.addWidget(self.x_trends_check, 4, 1)
        view_grid.addWidget(self.x_lines_check, 2, 1)
        view_grid.addWidget(self.x_color_check, 3, 1)
        view_grid.addWidget(self.minor_grid_check, 8, 0)
        view_grid.addWidget(self.major_grid_check, 7, 0)
        view_grid.addWidget(self.timing_grid_check, 9, 0)
        view_grid.addWidget(self.aims_check, 7, 1)
        view_grid.addWidget(self.timing_floor_check, 9, 1)
        view_grid.addWidget(self.phase_lines_check, 8, 1)

        # Setting initial states of checkboxes
        for checkbox in [self.minor_grid_check, self.major_grid_check, self.dots_check, self.xs_check,
                         self.dot_trends_check, self.x_trends_check, self.phase_lines_check,
                         self.aims_check, self.timing_floor_check]:
            checkbox.setChecked(True)

        for checkbox in [self.timing_grid_check, self.dot_lines_check, self.x_lines_check,
                         self.dot_color_check, self.x_color_check]:
            checkbox.setChecked(False)

        # Connect checkboxes to figure manager methods for handling changes
        self.dots_check.stateChanged.connect(self.figure_manager.view_dots)
        self.xs_check.stateChanged.connect(self.figure_manager.view_xs)
        self.minor_grid_check.stateChanged.connect(self.figure_manager.view_minor_gridlines)
        self.major_grid_check.stateChanged.connect(self.figure_manager.view_major_gridlines)
        self.timing_floor_check.stateChanged.connect(self.figure_manager.view_floor)
        self.phase_lines_check.stateChanged.connect(self.figure_manager.view_phase_lines)
        self.timing_grid_check.stateChanged.connect(self.figure_manager.view_floor_grid)
        self.aims_check.stateChanged.connect(self.figure_manager.view_aims)
        self.dot_trends_check.stateChanged.connect(self.figure_manager.view_dot_trend)
        self.x_trends_check.stateChanged.connect(self.figure_manager.view_x_trend)
        self.dot_lines_check.stateChanged.connect(self.figure_manager.view_dot_lines)
        self.x_lines_check.stateChanged.connect(self.figure_manager.view_x_lines)
        self.dot_color_check.stateChanged.connect(self.figure_manager.view_color_dots)
        self.x_color_check.stateChanged.connect(self.figure_manager.view_color_xs)

        # Credit lines button
        credit_lines_btn = QPushButton("Credit lines")
        credit_lines_btn.clicked.connect(self.credit_lines_popup)
        self.layout.addLayout(view_grid)
        self.layout.addWidget(credit_lines_btn)

        # Call the method to check the condition and update checkbox states
        self.update_timing_checkboxes()

    def credit_lines_popup(self):
        if self.dialog.exec_() == QDialog.Accepted:  # Check if the dialog was accepted
            r1, r2, r3 = self.dialog.get_inputs()  # Retrieve the inputs
            self.dialog.credit_row1 = r1
            self.dialog.credit_row2 = r2
            self.dialog.credit_row3 = r3
            self.figure_manager.view_update_credit_lines(r1, r2, r3)

    def update_timing_checkboxes(self):
        # Replace the following condition with your actual condition
        condition = 'Minute' in self.data_manager.user_preferences['chart_type']
        self.timing_floor_check.setEnabled(condition)
        self.timing_grid_check.setEnabled(condition)


class ManualModeTemplate(ModeWidget):
    def init_ui(self):
        self.create_radio_buttons()
        self.create_count_input()
        self.additional_ui_elements()
        self.create_date_input()
        self.create_manual_buttons()
        self.create_label_coordinates()
        self.layout.addStretch()

    def create_radio_buttons(self):
        radio_layout = QHBoxLayout()
        radio_dot = QRadioButton("Dots")
        radio_x = QRadioButton("Xs")
        radio_dot.setChecked(True)

        radio_layout.addWidget(radio_dot)
        radio_layout.addWidget(radio_x)
        self.layout.addLayout(radio_layout)

        radio_dot.toggled.connect(lambda checked: setattr(self.figure_manager, 'point_type', True) if checked else None)
        radio_x.toggled.connect(lambda checked: setattr(self.figure_manager, 'point_type', False) if checked else None)

    def create_count_input(self):
        validator = QDoubleValidator(0.0, 9999.99, 2)
        label_manual_count = QLabel('Count')
        count_input = QLineEdit('')
        count_input.setValidator(validator)
        self.layout.addWidget(label_manual_count)
        self.layout.addWidget(count_input)
        self.count_input = count_input

    def additional_ui_elements(self):
        # This method is meant to be overridden in subclasses to add additional UI elements.
        pass

    def create_date_input(self):
        # To be called only in subclasses where a date input is needed
        date_input = QDateEdit()
        date_input.setDate(QDate.currentDate())
        date_input.setCalendarPopup(True)
        date_input.setDisplayFormat("dd-MM-yyyy")
        self.layout.addWidget(QLabel('Date'))
        self.layout.addWidget(date_input)
        self.date_input = date_input

    def create_manual_buttons(self):
        manual_buttons_layout = QHBoxLayout()
        add_button = QPushButton('Add')
        undo_button = QPushButton('Undo')
        manual_buttons_layout.addWidget(add_button)
        manual_buttons_layout.addWidget(undo_button)
        self.layout.addLayout(manual_buttons_layout)

        add_button.clicked.connect(self.add_entry)
        undo_button.clicked.connect(self.figure_manager.manual_undo_point)
        self.add_button = add_button
        self.undo_button = undo_button

    def create_label_coordinates(self):
        label_xy_coordinates = QLabel('')
        self.layout.addWidget(label_xy_coordinates)

    def add_entry(self):
        raise NotImplementedError("Subclasses should implement this method")


class ManualModeWidgetDailyMinute(ManualModeTemplate):
    def additional_ui_elements(self):
        self.create_time_inputs()

    def create_time_inputs(self):
        validator = QDoubleValidator(0.0, 9999.99, 2)
        time_input_layout = QHBoxLayout()
        self.hour_input = self.create_time_input("Hour", validator)
        self.min_input = self.create_time_input("Min", validator)
        self.sec_input = self.create_time_input("Sec", validator)
        time_input_layout.addLayout(self.hour_input)
        time_input_layout.addLayout(self.min_input)
        time_input_layout.addLayout(self.sec_input)
        self.layout.addLayout(time_input_layout)

    def add_entry(self):
        self.figure_manager.manual_plot_form_minutes(
            self.count_input.text(),
            self.hour_input.itemAt(1).widget().text(),
            self.min_input.itemAt(1).widget().text(),
            self.sec_input.itemAt(1).widget().text(),
            self.date_input.text()
        )

    def create_time_input(self, label_text, validator):
        layout = QVBoxLayout()
        label = QLabel(label_text)
        input_field = QLineEdit()
        input_field.setValidator(validator)
        layout.addWidget(label, 0, Qt.AlignCenter)
        layout.addWidget(input_field)
        return layout


class ManualModeWidgetDaily(ManualModeTemplate):
    def add_entry(self):
        self.figure_manager.manual_plot_form_date(
            self.count_input.text(),
            self.date_input.text()
        )


class ManualModeWidgetWeekly(ManualModeTemplate):
    def init_ui(self):
        self.create_radio_buttons()
        self.create_count_input()
        self.create_date_navigation()
        self.create_manual_buttons()
        self.create_label_coordinates()
        self.layout.addStretch()

    def create_date_navigation(self):
        date_layout = QHBoxLayout()
        self.previous_button = QPushButton('<')
        self.next_button = QPushButton('>')
        self.date_label = QLabel()
        self.current_sunday = self.get_nearest_sunday(QDate.currentDate())

        self.update_date_label()

        date_layout.addWidget(self.previous_button)
        date_layout.addWidget(self.date_label)
        date_layout.addWidget(self.next_button)
        self.layout.addLayout(date_layout)

        self.previous_button.clicked.connect(self.show_previous_sunday)
        self.next_button.clicked.connect(self.show_next_sunday)

    def get_nearest_sunday(self, current_date):
        current_day_of_week = current_date.dayOfWeek()
        return current_date.addDays(7 - current_day_of_week if current_day_of_week != 7 else 0)

    def update_date_label(self):
        week_number = self.current_sunday.weekNumber()[0]
        month = self.current_sunday.toString("MMMM")
        year = self.current_sunday.toString("yy")
        self.date_label.setText(f"W {week_number}, {month}, {year}")

    def show_previous_sunday(self):
        self.current_sunday = self.current_sunday.addDays(-7)
        self.update_date_label()

    def show_next_sunday(self):
        self.current_sunday = self.current_sunday.addDays(7)
        self.update_date_label()

    def add_entry(self):
        self.figure_manager.manual_plot_form_date(
            self.count_input.text(),
            self.current_sunday.toString("dd-MM-yyyy")
        )


class ManualModeWidgetWeeklyMinute(ManualModeWidgetWeekly):
    def init_ui(self):
        self.create_radio_buttons()
        self.create_count_input()
        self.create_time_inputs()
        self.create_date_navigation()
        self.create_manual_buttons()
        self.create_label_coordinates()
        self.layout.addStretch()

    def create_time_inputs(self):
        validator = QDoubleValidator(0.0, 9999.99, 2)
        time_input_layout = QHBoxLayout()
        self.hour_input = self.create_time_input("Hour", validator)
        self.min_input = self.create_time_input("Min", validator)
        self.sec_input = self.create_time_input("Sec", validator)
        time_input_layout.addLayout(self.hour_input)
        time_input_layout.addLayout(self.min_input)
        time_input_layout.addLayout(self.sec_input)
        self.layout.addLayout(time_input_layout)

    def add_entry(self):
        self.figure_manager.manual_plot_form_minutes(
            self.count_input.text(),
            self.hour_input.itemAt(1).widget().text(),
            self.min_input.itemAt(1).widget().text(),
            self.sec_input.itemAt(1).widget().text(),
            self.current_sunday.toString("dd-MM-yyyy")
        )

    def create_time_input(self, label_text, validator):
        layout = QVBoxLayout()
        label = QLabel(label_text)
        input_field = QLineEdit()
        input_field.setValidator(validator)
        layout.addWidget(label, 0, Qt.AlignCenter)
        layout.addWidget(input_field)
        return layout


class ManualModeWidgetMonthly(ManualModeTemplate):
    def init_ui(self):
        self.create_radio_buttons()
        self.create_count_input()
        self.create_date_navigation()
        self.create_manual_buttons()
        self.create_label_coordinates()
        self.layout.addStretch()

    def create_date_navigation(self):
        date_layout = QHBoxLayout()
        self.previous_button = QPushButton('<')
        self.next_button = QPushButton('>')
        self.date_label = QLabel()
        self.current_date = self.get_last_day_of_month(QDate.currentDate())

        self.update_date_label()

        date_layout.addWidget(self.previous_button)
        date_layout.addWidget(self.date_label)
        date_layout.addWidget(self.next_button)
        self.layout.addLayout(date_layout)

        self.previous_button.clicked.connect(self.show_previous_month)
        self.next_button.clicked.connect(self.show_next_month)

    def get_last_day_of_month(self, date):
        next_month = date.addMonths(1)
        first_day_next_month = QDate(next_month.year(), next_month.month(), 1)
        return first_day_next_month.addDays(-1)

    def update_date_label(self):
        month = self.current_date.toString("MM")
        year = self.current_date.toString("yy")
        self.date_label.setText(f"{month}, {year}")

    def show_previous_month(self):
        self.current_date = self.current_date.addMonths(-1)
        self.current_date = self.get_last_day_of_month(self.current_date)
        self.update_date_label()

    def show_next_month(self):
        self.current_date = self.current_date.addMonths(1)
        self.current_date = self.get_last_day_of_month(self.current_date)
        self.update_date_label()

    def add_entry(self):
        self.figure_manager.manual_plot_form_date(
            self.count_input.text(),
            self.current_date.toString("dd-MM-yyyy")
        )


class ManualModeWidgetMonthlyMinute(ManualModeTemplate):
    def init_ui(self):
        self.create_radio_buttons()
        self.create_count_input()
        self.create_time_inputs()
        self.create_date_navigation()
        self.create_manual_buttons()
        self.create_label_coordinates()
        self.layout.addStretch()

    def create_date_navigation(self):
        date_layout = QHBoxLayout()
        self.previous_button = QPushButton('<')
        self.next_button = QPushButton('>')
        self.date_label = QLabel()
        self.current_date = self.get_last_day_of_month(QDate.currentDate())

        self.update_date_label()

        date_layout.addWidget(self.previous_button)
        date_layout.addWidget(self.date_label)
        date_layout.addWidget(self.next_button)
        self.layout.addLayout(date_layout)

        self.previous_button.clicked.connect(self.show_previous_month)
        self.next_button.clicked.connect(self.show_next_month)

    def get_last_day_of_month(self, date):
        next_month = date.addMonths(1)
        first_day_next_month = QDate(next_month.year(), next_month.month(), 1)
        return first_day_next_month.addDays(-1)

    def update_date_label(self):
        month = self.current_date.toString("MM")
        year = self.current_date.toString("yy")
        self.date_label.setText(f"{month}, {year}")

    def show_previous_month(self):
        self.current_date = self.current_date.addMonths(-1)
        self.current_date = self.get_last_day_of_month(self.current_date)
        self.update_date_label()

    def show_next_month(self):
        self.current_date = self.current_date.addMonths(1)
        self.current_date = self.get_last_day_of_month(self.current_date)
        self.update_date_label()

    def create_time_inputs(self):
        validator = QDoubleValidator(0.0, 9999.99, 2)
        time_input_layout = QHBoxLayout()
        self.hour_input = self.create_time_input("Hour", validator)
        self.min_input = self.create_time_input("Min", validator)
        self.sec_input = self.create_time_input("Sec", validator)
        time_input_layout.addLayout(self.hour_input)
        time_input_layout.addLayout(self.min_input)
        time_input_layout.addLayout(self.sec_input)
        self.layout.addLayout(time_input_layout)

    def create_time_input(self, label_text, validator):
        layout = QVBoxLayout()
        label = QLabel(label_text)
        input_field = QLineEdit()
        input_field.setValidator(validator)
        layout.addWidget(label, 0, Qt.AlignCenter)
        layout.addWidget(input_field)
        return layout

    def add_entry(self):
        self.figure_manager.manual_plot_form_minutes(
            self.count_input.text(),
            self.hour_input.itemAt(1).widget().text(),
            self.min_input.itemAt(1).widget().text(),
            self.sec_input.itemAt(1).widget().text(),
            self.current_date.toString("dd-MM-yyyy")
        )


class PhaseModeWidget(ModeWidget):
    def init_ui(self):
        # Creating label and input for phase change description
        phase_change_label = QLabel('Change')
        self.phase_change_input = QLineEdit('')
        self.layout.addWidget(phase_change_label)
        self.layout.addWidget(self.phase_change_input)

        # Y-value input
        phase_label_y = QLabel('Y-value')
        self.phase_y_input = QLineEdit('500')  # Default value set to 500
        validator = QDoubleValidator(0.0, 9999.99, 4)
        self.phase_y_input.setValidator(validator)
        self.layout.addWidget(phase_label_y)
        self.layout.addWidget(self.phase_y_input)

        # Date input setup
        phase_label_date = QLabel('Date')
        self.phase_date_input = QDateEdit()
        self.phase_date_input.setDate(QDate.currentDate())
        self.phase_date_input.setCalendarPopup(True)
        self.phase_date_input.setDisplayFormat("dd-MM-yyyy")
        self.layout.addWidget(phase_label_date)
        self.layout.addWidget(self.phase_date_input)

        # Buttons for adding and undoing phase lines
        phase_line_button_layout = QHBoxLayout()
        add_phase_line_btn = QPushButton('Add')
        undo_phase_line_btn = QPushButton('Undo')
        phase_line_button_layout.addWidget(add_phase_line_btn)
        phase_line_button_layout.addWidget(undo_phase_line_btn)
        self.layout.addLayout(phase_line_button_layout)

        # Connect buttons to figure manager methods
        add_phase_line_btn.clicked.connect(lambda: self.figure_manager.phase_line_from_form(
            self.phase_y_input.text(),
            self.phase_change_input.text(),
            self.phase_date_input.text()
        ))
        undo_phase_line_btn.clicked.connect(self.figure_manager.phase_undo_line)

        # Eliminate any extra vertical stretches
        self.layout.addStretch()


class AimModeWidget(ModeWidget):
    def init_ui(self):

        # Note input for aim
        aim_target_label = QLabel('Note')
        self.aim_target_input = QLineEdit('')
        self.layout.addWidget(aim_target_label)
        self.layout.addWidget(self.aim_target_input)

        # Y-value input for targeting
        aim_label_y = QLabel('Target')
        self.aim_y_input = QLineEdit('')
        self.aim_y_input.setValidator(QDoubleValidator(0.0, 9999.99, 4))
        self.layout.addWidget(aim_label_y)
        self.layout.addWidget(self.aim_y_input)

        # Start date input
        aim_label_start_date = QLabel('Start')
        self.aim_start_date_input = QDateEdit()
        self.aim_start_date_input.setDate(QDate.currentDate())
        self.aim_start_date_input.setCalendarPopup(True)
        self.aim_start_date_input.setDisplayFormat("dd-MM-yyyy")
        self.layout.addWidget(aim_label_start_date)
        self.layout.addWidget(self.aim_start_date_input)

        # Deadline date input
        aim_label_end_date = QLabel('Deadline')
        self.aim_end_date_input = QDateEdit()
        self.aim_end_date_input.setDate(QDate.currentDate())
        self.aim_end_date_input.setCalendarPopup(True)
        self.aim_end_date_input.setDisplayFormat("dd-MM-yyyy")
        self.layout.addWidget(aim_label_end_date)
        self.layout.addWidget(self.aim_end_date_input)

        # Add and Undo buttons for setting aims
        aim_line_button_layout = QHBoxLayout()
        add_aim_line_btn = QPushButton('Add')
        undo_aim_line_btn = QPushButton('Undo')
        aim_line_button_layout.addWidget(add_aim_line_btn)
        aim_line_button_layout.addWidget(undo_aim_line_btn)
        self.layout.addLayout(aim_line_button_layout)

        # Connect buttons to figure manager methods
        add_aim_line_btn.clicked.connect(lambda: self.figure_manager.aim_from_form(
            self.aim_target_input.text(),
            self.aim_y_input.text(),
            self.aim_start_date_input.text(),
            self.aim_end_date_input.text()
        ))
        undo_aim_line_btn.clicked.connect(self.figure_manager.aim_undo)


class TrendModeWidget(ModeWidget):
    def init_ui(self):

        # Creating a radio button group for selecting trend type
        radio_group_layout = QHBoxLayout()
        self.trend_radio_dot = QRadioButton("Dots")
        trend_radio_x = QRadioButton("Xs")
        trend_radio_group = QButtonGroup(self)
        trend_radio_group.addButton(self.trend_radio_dot)
        trend_radio_group.addButton(trend_radio_x)
        self.trend_radio_dot.setChecked(True)

        radio_group_layout.addWidget(self.trend_radio_dot)
        radio_group_layout.addWidget(trend_radio_x)
        self.layout.addLayout(radio_group_layout)

        # Date inputs for the start and end of the trend, arranged vertically
        date_input_layout = QVBoxLayout()

        date1_layout = QVBoxLayout()
        trend_label_start_date = QLabel('Date 1')
        self.trend_start_date_input = QDateEdit()
        self.trend_start_date_input.setDate(QDate.currentDate())
        self.trend_start_date_input.setCalendarPopup(True)
        self.trend_start_date_input.setDisplayFormat("dd-MM-yyyy")
        date1_layout.addWidget(trend_label_start_date)
        date1_layout.addWidget(self.trend_start_date_input)

        date2_layout = QVBoxLayout()
        trend_label_end_date = QLabel('Date 2')
        self.trend_end_date_input = QDateEdit()
        self.trend_end_date_input.setDate(QDate.currentDate())
        self.trend_end_date_input.setCalendarPopup(True)
        self.trend_end_date_input.setDisplayFormat("dd-MM-yyyy")
        date2_layout.addWidget(trend_label_end_date)
        date2_layout.addWidget(self.trend_end_date_input)

        # Add the date layouts to the main date input layout
        date_input_layout.addLayout(date1_layout)
        date_input_layout.addLayout(date2_layout)

        self.layout.addLayout(date_input_layout)

        # Buttons for managing trends
        trend_button_layout = QHBoxLayout()
        trend_add_btn = QPushButton('Add')
        self.trend_fit_btn = QPushButton('Fit')
        trend_undo_btn = QPushButton('Undo')

        trend_button_layout.addWidget(trend_add_btn)
        trend_button_layout.addWidget(self.trend_fit_btn)
        trend_button_layout.addWidget(trend_undo_btn)
        self.layout.addLayout(trend_button_layout)

        # Clean up when switching between point type
        self.trend_radio_dot.toggled.connect(self.figure_manager.trend_cleanup)
        trend_radio_x.toggled.connect(self.figure_manager.trend_cleanup)

        # Connect buttons to figure manager methods
        self.trend_fit_btn.clicked.connect(self.handle_fit_button)
        trend_add_btn.clicked.connect(lambda: self.figure_manager.trend_finalize(self.trend_radio_dot.isChecked()))
        trend_undo_btn.clicked.connect(lambda: self.figure_manager.trend_undo(self.trend_radio_dot.isChecked()))

        # Connect date changes to figure manager updates
        self.trend_start_date_input.dateChanged.connect(self.figure_manager.trend_date1_changed)
        self.trend_end_date_input.dateChanged.connect(self.figure_manager.trend_date2_changed)

        # Create a combo box for selecting the trend calculation method
        trend_method_group_layout = QVBoxLayout()
        trend_method_label = QLabel("Fit method")
        self.trend_method_combo = QComboBox()
        self.trend_method_combo.addItem('Least-squares')
        self.trend_method_combo.addItem('Quarter-intersect')
        self.trend_method_combo.addItem('Split-middle-line')
        self.trend_method_combo.setCurrentText(self.data_manager.user_preferences['fit_method'])
        self.trend_method_combo.currentIndexChanged.connect(
            lambda index: self.data_manager.user_preferences.update(
                {'fit_method': self.trend_method_combo.currentText()})
        )

        # SpinBox for Forward Projection
        forward_projection_label = QLabel("Forward projection")
        self.forward_projection_spinbox = QSpinBox()
        self.forward_projection_spinbox.setRange(0, 100)  # Set the range as required
        self.forward_projection_spinbox.setValue(self.data_manager.user_preferences.get('forward_projection', 0))
        self.forward_projection_spinbox.valueChanged.connect(
            lambda value: self.data_manager.user_preferences.update(
                {'forward_projection': value}
            )
        )

        # Add the label and the combo box layout to the group layout
        trend_method_group_layout.addWidget(trend_method_label)
        trend_method_group_layout.addWidget(self.trend_method_combo)

        # Add the forward projection label and spinbox to the group layout
        trend_method_group_layout.addWidget(forward_projection_label)
        trend_method_group_layout.addWidget(self.forward_projection_spinbox)

        # Add the combo box group layout to the main layout
        self.layout.addLayout(trend_method_group_layout)

        # Apply style sheet for spacing to the entire group
        trend_method_group_layout.setContentsMargins(0, 15, 0, 0)

        # Eliminate any extra vertical stretches
        self.layout.addStretch()

    def handle_fit_button(self):
        self.figure_manager.trend_fit(self.trend_radio_dot.isChecked())
        self.setFocus()  # Set focus back to the main window