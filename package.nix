{ lib,
  python,
  buildPythonApplication,
  poetry-core,
  requests,
  pyyaml,
  enlighten,
  pytestCheckHook,
  pytest,
  pytest-mock,
  wanda-version,
}:

buildPythonApplication rec {
  version = wanda-version;

  pname = "wanda";
  pyproject = true;

  src = with lib; cleanSourceWith {
    src = ./.;
    filter = path: type: !(hasSuffix ".nix" path);
  };

  build-system = [
    poetry-core
  ];

  dependencies = [
    requests
    pyyaml
    enlighten
  ];

  nativeCheckInputs = [
    pytestCheckHook
    pytest-mock
  ];

  pytestFlagsArray = [ "-m" "unit" ];

  optional-dependencies = [
    pytest
    pytest-mock
  ];

  passthru = {
    pythonEnv = python.withPackages (_: (dependencies ++ optional-dependencies));
  };
}
