

class InvalidRecordError(RuntimeError):

    def __init__(self, msg, control_number=None):
        super(InvalidRecordError, self).__init__(msg)
        self.control_number = control_number


class UnknownSchemeError(InvalidRecordError):

    def __init__(self, code=None, **kwargs):
        if code is None:
            msg = 'Could not find classification scheme or subject vocabulary code.'
        else:
            msg = 'Cannot generate URIs for unknown classification scheme or subject vocabulary "%s".' % code
        super(UnknownSchemeError, self).__init__(msg)
        self.code = code
        self.control_number = kwargs.get('control_number')
