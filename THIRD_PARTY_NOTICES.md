# Third-party components in the Windows executable

Tkinter++ 0.4.0 — Copyright (C) 2026 ortyanetty.
The application source is licensed under **GPL-3.0-only**; see `LICENSE`.
It is provided without warranty. The source and build instructions are available
at https://github.com/ortyanetty/TkinterPlusPlus/releases/tag/v0.4.0 .

The release includes Python, Qt, Tcl/Tk and the following dependencies. The optional
Windows installer also includes the unmodified Inno Setup runtime. Their
copyrights and licenses remain with their respective authors. The project
license does not replace these component licenses.

The release asset `TkinterPlusPlus-0.4.0-dependency-sources.zip` provides the
unmodified source distributions of PyQt6, SIP and PyInstaller. It is available
next to the executable without charge. The complete corresponding sources of
Qt, CPython, Tcl and Tk are available without charge at the version-specific
upstream locations listed below. Those components are used without source
modifications. The application source archive contains the application code
and build scripts needed to rebuild this executable.

| Component | Version | License / copyright | Corresponding source |
| --- | --- | --- | --- |
| Inno Setup (installer only) | 7.1.1 x64 | Inno Setup License; Jordan Russell and Martijn Laan; see licenses/INNO_SETUP_LICENSE.txt | https://github.com/jrsoftware/issrc/tree/is-7_1_1 |
| CPython | 3.14.8 | PSF License and included third-party notices; Python Software Foundation and contributors | https://www.python.org/ftp/python/3.14.8/Python-3.14.8.tar.xz |
| PyQt6 | 6.12.0 | GPLv3; Riverbank Computing Limited | https://pypi.org/project/PyQt6/6.12.0/#files |
| PyQt6-sip | 13.13.0 | SIP license; Riverbank Computing Limited | https://pypi.org/project/PyQt6-sip/13.13.0/#files |
| Qt | 6.12.0 | LGPLv3 and third-party notices; The Qt Company and contributors | https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/ |
| Tcl | 9.0.4 | Tcl license; Regents of the University of California, Sun Microsystems and contributors | https://prdownloads.sourceforge.net/tcl/tcl9.0.4-src.tar.gz |
| Tk | 9.0.4 | Tk license; Regents of the University of California, Sun Microsystems and contributors | https://prdownloads.sourceforge.net/tcl/tk9.0.4-src.tar.gz |
| PyInstaller bootloader | 6.22.3 | GPLv2-or-later with the bootloader exception | https://pypi.org/project/pyinstaller/6.22.3/#files |

Full license texts distributed with the executable are in its `licenses`
directory. The executable embeds these files with the program. The same files
are included in the source archive and repository. Qt includes additional
third-party software; see https://doc.qt.io/qt-6/licenses-used-in-qt.html .
The optional Qt software OpenGL renderer (`opengl32sw.dll`) is not bundled;
the editor uses the raster paint engine. Microsoft Visual C++ runtime files
retain Microsoft's redistribution terms and the Windows system libraries
remain supplied by Windows.

Build the application with `scripts/build_windows.ps1` and
`packaging/TkinterPlusPlus.spec`. To rebuild with modified Qt libraries, install
the corresponding PyQt6/Qt wheels or build those components from the linked
source first, then rebuild the executable with the same spec. No signing key
or activation service is required to run a rebuilt version.

Licensing references:
- https://www.riverbankcomputing.com/software/pyqt/intro
- https://www.riverbankcomputing.com/commercial/license-faq
- https://doc.qt.io/qt-6/licensing.html
- https://pyinstaller.org/en/stable/license.html
