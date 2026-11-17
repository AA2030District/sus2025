"""Optional progress callback shared by the updater scripts and worker."""
_reporter = None


def set_reporter(reporter):
    global _reporter
    _reporter = reporter


def report_progress(percent, message):
    if _reporter is not None:
        _reporter(percent, message)
