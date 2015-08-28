import dateutil.parser
import logging

LOG = logging.getLogger("pyalexa")

try:
    from flask import request, make_response, jsonify
except ImportError:
    LOG.warn("Could not import flask; functionality disabled")
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

    def __contains__(self, key):
        return key in self.attributes

    def get(self, key, default=None):
        return self.attributes.get(key, default)

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
    def __init__(self, request, *parts, end=False):
        self.end = end

        self.request = request

        if parts:
            self.parts = parts
        else:
            self.parts = []

    def packed(self):
        res = {
            "version": self.request.skill.version,
            "sessionAttributes": self.request.session.attributes,
            "response": {
                "shouldEndSession": self.end
            }
        }

        for part in self.parts:
            if part:
                res["response"].update(part.packed())

        return res

class Request:
    LAUNCH = "LaunchRequest"
    INTENT = "IntentRequest"
    SESSION_ENDED = "SessionEndedRequest"

    @classmethod
    def parse(cls, data):
        if "request" in data and "type" in data["request"]:
            LOG.debug("Parsing request")
            kind = data["request"]["type"]

            if kind == Request.LAUNCH:
                LOG.debug("Request is LaunchRequest")
                return LaunchRequest(data)
            elif kind == Request.INTENT:
                LOG.debug("Request is IntentRequest")
                return IntentRequest(data)
            elif kind == Request.SESSION_ENDED:
                LOG.debug("Request is SessionEndedRequest")
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

    def response(self, speech=None, reprompt=None, card=None, end=False):
        if isinstance(speech, str):
            speech = Speech(speech)
        if isinstance(reprompt, str):
            reprompt = Reprompt(reprompt)
        return Response(self, speech, reprompt, card, end=end).packed()

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

    def data(self):
        """Return combined dictionary of slots and session attributes.

        If there is a slot and session attribute with the same name,
the slot will take precedence.

        """
        res = dict(self.session.attributes)
        res.update(self.intent.slots)

        return res

    def save_slots(self, *names):
        """Add all or some slots as session attributes"""

        if names:
            LOG.debug("Saving slots %s", names)
            for name in names:
                self.session[name] = self.intent.slots[name]
        else:
            LOG.debug("Saving all slots")
            self.session.attributes.update(self.intent.slots)

class InvalidApplication(Exception):
    pass

class UnhandledRequestException(Exception):
    pass

class Skill:
    def __init__(self, config={}, schema={}, validate=True, app_id=None,
                 version="0.0.0"):
        self.config = config
        self.schema = schema

        if "validate" not in self.config:
            self.config["validate"] = validate

        if "app_id" not in self.config:
            self.config["app_id"] = app_id

        if "version" in self.config:
            version = self.config["version"]

        self.version = version

        self._intents = {}

        self.app_id = None

    # Passthrough Decorator
    def launch(self, target):
        self._on_launch = target

        LOG.debug("Registered %s as launch target", target)

        return target

    # Passthrough Decorator
    def end(self, target):
        self._on_end = target

        LOG.debug("Registered %s as session end target", target)

        return target

    # Passthrough Decorator
    def intent(self, *intent_names):
        def decorator(target=None, *args, **kwargs):
            LOG.debug("Registered %s as intent for targets %s", target, intent_names)
            for name in intent_names:
                self.register_intent(name, target)

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
                    LOG.exception("Received a request from the wrong application")
                    return make_response(("This application is not allowed to access this skill.", 403, []))
                except UnhandledRequestException as e:
                    LOG.exception("Received a request for an intent that does not exist")
                    return make_response((str(e), 404, []))
                except Exception as e:
                    LOG.exception("Unhandled exception in flask_target")
                    return make_response((str(e), 500, []))
        else:
            raise ImportError("Flask was not imported")
