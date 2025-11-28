{
  description = "Infrahub development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            pkgs.git
            pkgs.gh
            pkgs.vale
          ];

          shellHook = ''
            echo "Infrahub development environment"
            echo "Available tools:"
            echo "  - git: $(git --version)"
            echo "  - gh (GitHub CLI): $(gh --version | head -n1)"
            echo "  - vale (prose linter): $(vale --version)"
          '';
        };
      }
    );
}
