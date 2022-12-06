{
  description = "wanda - WAN Data Aggregator";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/22.11";
  inputs.poetry2nix = {
    url = "github:nix-community/poetry2nix";
    inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    {
      # Nixpkgs overlay providing the application
      overlay = nixpkgs.lib.composeManyExtensions [
        poetry2nix.overlay
        (final: prev: {
          # The application
          wanda = prev.poetry2nix.mkPoetryApplication {
            projectDir = ./.;
          };
        })
      ];
    } // (flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [ self.overlay ];
        };
      in
      {
        packages = {
          wanda = pkgs.wanda;
          default = pkgs.wanda;
        };

        devShell = pkgs.mkShell {
          buildInputs = with pkgs; [
            bgpq4
            wanda.dependencyEnv
          ];
        };
      }));
}
