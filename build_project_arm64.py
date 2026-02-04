from build_project_base import main_py
import clean
import buildzip
from setup_ccache import setup_ccache
target="com.pyquick.converter"
from patch import enable
from plistedit import add_utf_info
if __name__ == "__main__":
    clean.clean()
    main_py()
    #enable(target)
    add_utf_info()
    buildzip.build_zip()