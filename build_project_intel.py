from build_nk import main
import clean
import buildzip
from setup_ccache import setup_ccache

from plistedit import add_utf_info
if __name__ == "__main__":
    clean.clean()
    main()
    add_utf_info()
    buildzip.build_zip_intel()