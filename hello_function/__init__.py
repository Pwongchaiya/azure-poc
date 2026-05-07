import logging
import azure.functions as func


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("hello_function triggered.")

    # Optionally greet by name if a query param or JSON body is provided.
    name = req.params.get("name")

    if not name:
        try:
            body = req.get_json()
            name = body.get("name")
        except ValueError:
            # Body is absent or not valid JSON — that's fine, name stays None.
            pass

    greeting = f"Hello, {name}!" if name else "Hello from Azure Functions I made a change that will when i push to main!"

    return func.HttpResponse(
        greeting,
        status_code=200,
        mimetype="text/plain",
    )