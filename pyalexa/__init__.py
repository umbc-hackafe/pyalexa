import dateutil.parser

try:
    from flask import request, make_response, jsonify
except ImportError:
    pass

def _alexa_dict(mapping={}):
    return {k: v.get("value", None) for k, v in mapping.items()}

class Session:
    def __init__(self, data):
        self.new = data.get("new", False)
        self.id = data.get("sessionId")
        self.attributes = _alexa_dict(data.get("attributes", {}))
        self.application_id = data.get("application", {}).get("applicationId")
        self.user_id = data.get("user", {}).get("userId")

    def __getitem__(self, key):
        """Shortcut for getting attributes"""
        return self.attributes.get(key)

    def __setitem__(self, key, val):
        self.attributes.set(key, val)

    def __delitem__(self, key):
        del self.attributes[key]

    def items(self):
        return self.attributes.items()

class ResponsePart:
    def packed(self):
        return {}

class Speech(ResponsePart):
    PLAIN_TEXT = "PlainText"

    def __init__(self, text, type=None):
        if not type:
            type = Speech.PLAIN_TEXT

        self.text = text
        self.type = type

    def packed(self):
        return {
            "outputSpeech": {
                "type": self.type,
                "text": self.text
            }
        }

class Reprompt(ResponsePart):
    def __init__(self, output):
        if isinstance(output, str):
            self.output = Speech(output)
        else:
            self.output = output

    def packed(self):
        return {
            "reprompt": self.output.packed()
        }

class Card:
    SIMPLE = "Simple"
    def __init__(self, title, content, type=None):
        if not type:
            type = Card.SIMPLE
        self.title = title
        self.content = content
        self.type = type

    def packed(self):
        return {
            "card": {
                "type": self.type,
                "title": self.title,
                "content": self.content
            }
        }

class Response:
    def __init__(self, request, end=False, *parts):
        self.end = end

        self.request = request

        if parts:
            self.parts = parts
        else:
            self.parts = []

    def packed(self):
        res = {
            "version": self.skill,
            "sessionAttributes": self.request.session.attributes,
            "response": {
                "shouldEndSession": self.end
            }
        }

        for part in self.parts:
            res["response"].update(part.packed())

        return res

class Request:
    LAUNCH = "LaunchRequest"
    INTENT = "IntentRequest"
    SESSION_ENDED = "SessionEndedRequest"

    @classmethod
    def parse(cls, data):
        if "request" in data and "type" in data["request"]:
            kind = data["request"]["type"]

            if kind == Request.LAUNCH:
                return LaunchRequest(data)
            elif kind == Request.INTENT:
                return IntentRequest(data)
            elif kind == Request.SESSION_ENDED:
                return SessionEndedRequest(data)
        raise ValueError("data is not a valid request")

    def __init__(self, data):
        req = data.get("request")
        
        self.request_type = req.get("type")
        self.id = req.get("requestId")
        self.timestamp = dateutil.parser.parse(req.get("timestamp"))

        self.version = data.get("version")
        self.session = Session(data.get("session", {}))

        self.headers = {}

    def response(self, end=False, speech=None, card=None, reprompt=None):
        return Response(self, speech, card, reprompt, end=end).packed()

class LaunchRequest(Request):
    """Apparently identical to Request in functionality."""
    pass

class SessionEndedRequest(Request):
    USER_INITIATED = "USER_INITIATED"
    ERORR = "ERROR"
    EXCEEDED_MAX_REPROMPTS = "EXCEEDED_MAX_REPROMPTS"

    def __init__(self, data):
        super().__init__(data)

        req = data.get("request", {})

        self.reason = req.get("reason")

class Intent:
    def __init__(self, data):
        self.slots = _alexa_dict(data.get("slots", {}))
        self.name = data.get("name")

class IntentRequest(Request):
    def __init__(self, data):
        super().__init__(data)

        req = data.get("request", {})
        self.intent = Intent(req.get("intent"))

class InvalidApplication(Exception):
    pass

class UnhandledRequestException(Exception):
    pass

class Skill:
    def __init__(self, config={}, schema={}, validate=True, app_id=None):
        self.config = config
        self.schema = schema

        if "validate" not in self.config:
            self.config["validate"] = validate

        if "app_id" not in self.config:
            self.config["app_id"] = app_id

        self._intents = {}

        self.app_id = None

    # Passthrough Decorator
    def launch(self, target):
        self._on_launch = target

        return target

    # Passthrough Decorator
    def end(self, target):
        self._on_end = target

        return target

    # Passthrough Decorator
    def intent(self, intent_name):
        def decorator(target=None, *args, **kwargs):
            self.register_intent(intent_name, target)
            return target
        return decorator

    def register_intent(self, name, target):
        self._intents[name] = target

    def validate_request(self, request):
        if self.config["validate"] and self.config["app_id"]:
            if self.config["app_id"] != request.app_id:
                raise InvalidApplication("App ID '{}' does not match configured value '{}'".format(request.app_id, self.config["app_id"]))

    def handle_request(self, data, headers={}):
        request = Request.parse(data)
        request.headers.update(headers)
        request.skill = self
        
        if request.request_type == Request.LAUNCH:
            if self._on_launch:
                return self._on_launch(request)
            else:
                raise UnhandledRequestException("LaunchRequest has no handler")
        elif request.request_type == Request.INTENT:
            name = request.intent.name
            if name in self._intents:
                return self._intents[name](request)
            else:
                raise UnhandledRequestException("IntentRequest {} has no handler".format(name))
        elif request.request_type == Request.SESSION_ENDED:
            if self._on_end:
                return self._on_end(request)
            else:
                raise UnhandledRequestException("SessionEndedRequest has no handler")

    def flask_target(self):
        if request:
            data = request.get_json()
            if data:
                try:
                    result = self.handle_request(data, dict(request.headers)) or Response(request)
                    return jsonify(result)
                except InvalidApplication:
                    return make_response(("This application is not allowed to access this skill.", 403, []))
                except UnhandledRequestException as e:
                    return make_response((str(e), 404, []))
                except Exception as e:
                    return make_response((str(e), 500, []))
        else:
            raise ImportError("Flask was not imported")
