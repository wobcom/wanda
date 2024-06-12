{
  description = "wanda - WAN Data Aggregator";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
  inputs.poetry2nix = {
    url = "github:nix-community/poetry2nix";
    inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    {
      # Nixpkgs overlay providing the application
      overlay = nixpkgs.lib.composeManyExtensions [
        poetry2nix.overlays.default
        (final: prev: {
          # The application
          wanda = prev.poetry2nix.mkPoetryApplication {
            projectDir = with final.lib; cleanSourceWith {
              src = ./.;
              filter = path: type: !(hasSuffix ".nix" path) && baseNameOf path != ".nix";
            };
          };

          # Used to run tests for wanda
          wandaTestEnv = prev.poetry2nix.mkPoetryEnv {
              projectDir = ./.;
          };

          wandaNixosTest = final.nixosTest (import ./nixos-test.nix);
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
          inherit (pkgs) wanda wandaNixosTest;
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
