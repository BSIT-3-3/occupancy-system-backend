from flasgger import Swagger

from api import register_blueprints
from cli import register_cli_commands
from database import create_app

app = create_app()
register_blueprints(app)
register_cli_commands(app)

swagger = Swagger(app)


if __name__ == "__main__":
    app.run(debug=False)
