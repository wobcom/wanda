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
    environment.systemPackages = with pkgs; [ wanda wandaTestEnv ];
  };

  testScript = { nodes }: let
    peeringmanagerUrl = "http://localhost:${toString nodes.machine.config.services.peering-manager.port}";
  in ''
    machine.start()
    machine.wait_for_unit("peering-manager.target")
    machine.wait_until_succeeds("journalctl --since -1m --unit peering-manager --grep Listening")

    machine.succeed("peering-manager-manage createsuperuser --no-input --username admin --email admin@example.com")

    api_token=machine.succeed(
        "peering-manager-manage shell -c \"from users.models import Token; from users.models import User; u=User.objects.get(email='admin@example.com'); t = Token.objects.create(user=u); print(t.key)\""
    ).strip()

    machine.succeed("PEERINGMANAGER_API_TOKEN=%s PEERINGMANAGER_URL=${peeringmanagerUrl} pytest ${pkgs.wanda.src}" % (api_token))
    machine.shutdown()
  '';
}
