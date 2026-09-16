{
  description = "Equation Golf development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";

      pkgs = import nixpkgs {
        inherit system;
      };
    in {
      devShells.${system}.default = pkgs.mkShell {
        packages = with pkgs; [
          nodejs_22
          python312
          uv
          git
        ];

        shellHook = ''
          echo "Equation Golf dev shell"
          echo "Node:   $(node --version)"
          echo "Python: $(python --version)"

          if [ -f .venv/bin/activate ]; then
            source .venv/bin/activate
            echo "Python venv activated"
          fi
        '';
      };
    };
}
