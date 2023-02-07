import typer

app = typer.Typer()


@app.command()
def config():
    pass


@app.command()
def all():
    print("Not implemented yet.")
