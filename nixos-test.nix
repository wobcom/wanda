{ lib, pkgs, ... }: {
  name = "peering-manager";

  meta = with lib.maintainers; {
    maintainers = [ yuka ];
  };

  nodes.machine = { ... }: {
    services.peering-manager = {
      enable = true;
      secretKeyFile = pkgs.writeText "secret" ''
        abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789
      '';
    };
    environment.systemPackages = with pkgs; [ wanda ];
  };

  testScript = { nodes }: let
    peeringmanagerUrl = "http://localhost:${toString nodes.machine.config.services.peering-manager.port}";
  in ''
    machine.start()
    machine.wait_for_unit("peering-manager.target")
    machine.wait_until_succeeds("journalctl --since -1m --unit peering-manager --grep Listening")

    machine.succeed("peering-manager-manage loaddata ${./testdata.json}")

    machine.succeed("PEERINGMANAGER_API_TOKEN=123 PEERINGMANAGER_URL=${peeringmanagerUrl} wanda" % (api_token))
  '';
}
