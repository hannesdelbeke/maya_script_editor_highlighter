import keyword
import logging

from maya import OpenMayaUI, cmds
try:
    from PySide2 import QtCore, QtGui, QtWidgets
    from shiboken2 import wrapInstance
    __QT_BINDINGS__ = 'PySide2'
except ImportError:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import wrapInstance
    __QT_BINDINGS__ = 'PySide6'


if __QT_BINDINGS__ == 'PySide6':
    scriptEditorType = QtWidgets.QPlainTextEdit
else:
    scriptEditorType = QtWidgets.QTextEdit


def maya_useNewAPI():  # noqa
    pass  # dummy method to tell Maya this plugin uses Maya Python API 2.0


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


COLOURS = {
    'default': QtGui.QColor(200, 200, 200),
    'debug': QtGui.QColor(70, 200, 255),
    'success': QtGui.QColor(16, 255, 8),
    'warning': QtGui.QColor(255, 160, 0),
    'error': QtGui.QColor(255, 0, 0),
    'traceback': QtGui.QColor(150, 160, 255),
}

# Modified word boundary to exclude dashes, underscores, dots and commas as boundaries.
MODIFIED_WORD_BOUNDARY = r'\b(?<!\-|\_|\.|\,)'


def get_rx_rule(name, pattern=None, case_sensitive=False):
    # Use given pattern or use the name in a modified word boundary.
    pattern = pattern or r'{0}{1}{0}'.format(MODIFIED_WORD_BOUNDARY, name)
    rx_pattern = QtCore.QRegularExpression(pattern)
    if not case_sensitive:
        rx_pattern.setPatternOptions(QtCore.QRegularExpression.CaseInsensitiveOption)

    rx_format = QtGui.QTextCharFormat()
    rx_format.setForeground(COLOURS[name])
    return rx_pattern, rx_format


# TODO : finish implementing python keyword highlighting in stack traces
class PythonSyntaxRules(object):

    keyword_format = QtGui.QTextCharFormat()
    keyword_format.setFontWeight(QtGui.QFont.Bold)
    keyword_format.setForeground(COLOURS['warning'])

    # For some reason this doesn't work as a list comprehension and yields an "undefined" for
    # keyword format in the following list comprehension :
    # Rules = [(QRegularExpression(r"((\s){}(\s))".format(keyword)), keyword_format) for keyword in keywords]
    # We also here just put all matching works into a single pattern for performance.
    Rules = [
        (
            QtCore.QRegularExpression(r'{0}(?:{1}){0}'.format(MODIFIED_WORD_BOUNDARY, '|'.join(keyword.kwlist))),
            keyword_format
        )
    ]


class StdOut_Syntax(QtGui.QSyntaxHighlighter):

    default_format = QtGui.QTextCharFormat()
    default_format.setForeground(COLOURS['default'])

    rx_traceback_start, traceback_format = get_rx_rule(
        'traceback',
        r'Traceback \(most recent call last\)\:',
        case_sensitive=True,
    )

    Rules = [
        get_rx_rule('error'),
        get_rx_rule('warning'),
        get_rx_rule('success'),
        get_rx_rule('debug'),
    ]

    BlockState_Normal = 0
    BlockState_Traceback = 1

    @staticmethod
    def __pattern_match(text, rx_pattern):
        if __QT_BINDINGS__ == 'PySide6':
            match = rx_pattern.match(text).hasMatch()
        else:
            match = rx_pattern.indexIn(text)
        return bool(match)

    def highlightBlock(self, line):
        self.setCurrentBlockState(self.BlockState_Normal)
        if self.isTraceback(line):
            self.setFormat(0, len(line), self.traceback_format)
            self.setCurrentBlockState(self.BlockState_Traceback)
        else:
            self.lineFormatting(line)

    def lineFormatting(self, line):
        for rx_pattern, formatting in self.Rules:
            if self.__pattern_match(line, rx_pattern):
                self.setFormat(0, len(line), formatting)
                break

    def isTraceback(self, line):
        previousBlockState = self.previousBlockState()
        if (previousBlockState == self.BlockState_Normal and
                self.__pattern_match(line, self.rx_traceback_start)):
            return True
        elif (previousBlockState == self.BlockState_Traceback and
              line.startswith("# ") and
              not any(self.__pattern_match(line, rule[0]) for rule in self.Rules)):
            return True
        return False


def __se_highlight():
    logger.debug("Attaching highlighter")
    i = 1
    while True:
        script_editor_output_name = "cmdScrollFieldReporter{}".format(i)
        script_editor_output_object = OpenMayaUI.MQtUtil.findControl(script_editor_output_name)
        if not script_editor_output_object:
            break

        script_editor_output_widget = wrapInstance(int(script_editor_output_object), scriptEditorType)
        logger.debug(script_editor_output_widget)
        document = script_editor_output_widget.document()
        if not document.findChild(StdOut_Syntax):
            StdOut_Syntax(document)
            logger.debug("Done attaching highlighter to : %s", script_editor_output_widget)
        i += 1


def __se_remove_highlight():
    logger.debug('Detaching highlighter')
    i = 1
    while True:
        script_editor_output_name = "cmdScrollFieldReporter{}".format(i)
        script_editor_output_object = OpenMayaUI.MQtUtil.findControl(script_editor_output_name)
        if not script_editor_output_object:
            break

        script_editor_output_widget = wrapInstance(int(script_editor_output_object), scriptEditorType)
        logger.debug(script_editor_output_widget)
        document = script_editor_output_widget.document()
        highlighter = document.findChild(StdOut_Syntax)
        if highlighter:
            highlighter.setParent(None)
            highlighter.deleteLater()
            logger.debug("Done detaching highlighter from : %s", script_editor_output_widget)
        i += 1


__qt_focus_change_callback = {"cmdScrollFieldReporter": __se_highlight}


def __on_focus_changed(old_widget, new_widget):
    if not new_widget:
        return

    widgetName = new_widget.objectName()
    for callback in __qt_focus_change_callback:
        if widgetName.startswith(callback):
            __qt_focus_change_callback[callback]()


def setup_highlighter():
    try:
        app = QtWidgets.QApplication.instance()
        app.focusChanged.connect(__on_focus_changed)
        __se_highlight()
    except Exception as e:
        logger.warning('Failed to setup highlighter: %s', e, exc_info=True)


def teardown_highlighter():
    try:
        __se_remove_highlight()
        app = QtWidgets.QApplication.instance()
        app.focusChanged.disconnect(__on_focus_changed)
    except Exception as e:
        logger.warning('Failed to teardown highlighter: %s', e, exc_info=True)


def initializePlugin(plugin):
    cmds.evalDeferred(setup_highlighter)


def uninitializePlugin(plugin):
    teardown_highlighter()
