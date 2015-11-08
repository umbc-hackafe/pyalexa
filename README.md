# pyalexa
Simple Python API for granting custom skills to the Amazon Echo (Alexa)

# Design #

pyalexa uses [flask]-style decorators to mark functions that
handle a particular intent.

[flask]: http://flask.pocoo.org/

# Examples #

## Declaring a skill ##

To declare a skill, you will need your Amazon app ID, something like
`amzn1.echo-sdk-ams.app.12345678-9abc-def0-1234-56789abcdef0`.
Then, just create a `Skill` object:

    from pyalexa import Skill

    skill = Skill(app_id='amzn1.echo-sdk-ams.app.12345678-9abc-def0-1234-56789abcdef0',
	              version='1.0')

Intents are handled using decorators, in the style of the popular
flask library. There are three decorators provided: `launch`, for the
[LaunchRequest], `end` for [SessionEndedRequest], and `intent` for
[IntentRequest]s. Here's a pyalexa version of HelloWorld, from Amazon's
[sample skills].

    from pyalexa import Skill, Card

    skill = Skill(app_id='amzn1.echo-sdk-ams.app.12345678-9abc-def0-1234-56789abcdef0')

    @skill.launch
    def launch(request):
        return request.response(
            speech="Welcome to pyalexa, you can say hello",
            reprompt="You can say hello"
        )

    @skill.end
    def end(request):
        print("We can do cleanup stuff here")

    @skill.intent("HelloWorldIntent")
    def hello_world(request):
        return request.response(
            card=Card("Greeter", "Hello World!")
            speech="Hello world!"
        )

    @skill.intent("HelpIntent")
	def help_intent(request):
        return request.response(
            text="You can say hello to me!",
            reprompt="You can say hello to me!"
        )

[LaunchRequest]: https://developer.amazon.com/public/solutions/alexa/alexa-skills-kit/docs/alexa-skills-kit-interface-reference#LaunchRequest
[SessionEndedRequest]: https://developer.amazon.com/public/solutions/alexa/alexa-skills-kit/docs/alexa-skills-kit-interface-reference#SessionEndedRequest
[SessionEndedRequest]: https://developer.amazon.com/public/solutions/alexa/alexa-skills-kit/docs/alexa-skills-kit-interface-reference#IntentRequest
[sample skills]: https://developer.amazon.com/public/solutions/alexa/alexa-skills-kit/docs/using-the-alexa-skills-kit-samples
