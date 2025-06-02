{
  description = "wanda - WAN Data Aggregator";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";

  outputs = { self, nixpkgs, flake-utils }:
    {
      # Nixpkgs overlay providing the application
      overlay = (final: prev: let
        pyprojectFile = builtins.fromTOML (builtins.readFile ./pyproject.toml);
        # We absolutly want to ship our own deps, so we use our own python and our own python3Packages.
        pkgs = nixpkgs.legacyPackages.${final.stdenv.hostPlatform.system};
      in rec {
        wanda = pkgs.python3.pkgs.callPackage ./package.nix { wanda-version = pyprojectFile.tool.poetry.version; };
        wandaTest = final.callPackage ./nixos-test.nix { };
      });
    } // (flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [ self.overlay ];
        };
      in
      {
        packages = {
          inherit (pkgs) wanda wandaTest;
          default = pkgs.wanda;
        };

        checks = {
          inherit (pkgs) wandaTest;
        };

        devShell = pkgs.mkShell {
          buildInputs = with pkgs; [
            bgpq4
            wanda.pythonEnv
          ];
        };
      }));
}
