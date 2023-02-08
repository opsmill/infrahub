import typer

app = typer.Typer()


@app.command()
def load():
    pass


@app.command()
def migrate():
    print("Not implemented yet.")
