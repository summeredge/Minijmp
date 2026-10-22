import os
import sys
#########################
from .core_orig import statusBar as SBar_orig
from .core_orig import Table as Table_orig
from . import config

themes = {
    'dark': {
        'cellbackgr': 'gray25',
        'grid_color': 'gray50',
        'textcolor': '#f2eeeb',
        'rowselectedcolor': '#ed9252',
        'colselectedcolor': '#3d65d4'},
    'bold': {
        'cellbackgr': 'white',
        'grid_color': 'gray50',
        'textcolor': 'black',
        'rowselectedcolor': 'yellow',
        'colselectedcolor': '#e4e3e4'},
    'default': {
        'cellbackgr': '#F4F4F3',
        'grid_color': '#ABB1AD',
        'textcolor': 'black',
        'rowselectedcolor': '#E4DED4',
        'colselectedcolor': '#e4e3e4'}}

if getattr(sys, 'frozen', False):
    app_data = os.environ.get('LOCALAPPDATA') or os.path.join(
        os.path.expanduser('~'), 'AppData', 'Local')
    config_path = os.path.join(app_data, 'MiniJMP', 'log')
    sample_data_path = os.path.join(sys._MEIPASS, 'sample_data')
else:
    parent_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_path = os.path.join(parent_path, 'log')
    sample_data_path = os.path.join(parent_path, 'sample_data')
logfile = os.path.join(config_path, 'error.log')
os.makedirs(config_path, exist_ok=True)


class Table(Table_orig):
    def init_reserved(self):
        print("loading_path", os.getcwd())
        self.currentdir = sample_data_path
        print("current dir", self.currentdir)
        self.logfile = logfile
        return

    def loadPrefs(self, prefs=None):
        """Load preferences from defaults"""
        # Added to change default dir
        # This loadPrefs seems only be loaded when init
        self.init_reserved()
        ###
        options = config.load_options()
        config.apply_options(options, self)
        self.apply_system_theme()
        return


class statusBar(SBar_orig):
    """Status bar class"""
    pass
