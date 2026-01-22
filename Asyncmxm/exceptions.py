class MXMException(Exception):
    codes = {
        400: "The request had bad syntax or was inherently impossible to be satisfied.",
        401: "We have hit the Musixmatch API limit for today. Sorry, I can't do much about it, but you can set up a private one.",
        402: "The usage limit has been reached, either you exceeded per day requests limits or your balance is insufficient.",
        403: "You are not authorized to perform this operation.",
        404: "The requested resource was not found.",
        405: "The requested method was not found.",
        500: "Ops. Something were wrong.",
        503: "Our system is a bit busy at the moment and your request can't be satisfied.",
    }

    def __init__(self, status_code, message):
        """
        Initialize an MXMException with a status code and message.
        
        If `message` is truthy it is stored as the exception message; otherwise a default message is looked up from the class `codes` mapping using `status_code`, and `"Unknown Error"` is used if no mapping exists. The provided `status_code` and resulting `message` are stored on the instance as `status_code` and `message`.
        
        Parameters:
            status_code (int): HTTP-like status code used to select a default message when `message` is not provided.
            message (str | None): Custom error message to store; if falsy, a default from `codes` or `"Unknown Error"` will be used.
        """
        self.status_code = status_code
        if message:
            self.message = message
        else:
            self.message = self.codes.get(status_code) or "Unknown Error"

    def __str__(self):
        """
        Format the exception as a human-readable string.
        
        Returns:
            str: Formatted string "Error code: {status_code} - message: {message}" where `status_code` is the exception's status code and `message` is its message.
        """
        return f"Error code: {self.status_code} - message: {self.message}"