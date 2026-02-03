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
          buildInputs = with pkgs; [
            git
            gh
            lychee
            vale
            stdenv.cc.cc.lib
          ];

          shellHook = ''
            echo "Infrahub development environment"
            echo "Available tools:"
            echo "  - git: $(git --version)"
            echo "  - gh (GitHub CLI): $(gh --version | head -n1)"
            echo "  - lychee (link checker): $(lychee --version)"
            echo "  - vale (prose linter): $(vale --version)"
          '';
          LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
            pkgs.stdenv.cc.cc.lib
          ];
        };
      }
    );
}
