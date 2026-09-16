from datetime import date

from sqlalchemy import select

from .database import SessionLocal
from .models import Challenge


CHALLENGES = [
    Challenge(
        challenge_date=date(2026, 9, 13),

        target_expr=(
            "0.7*sin(1.3*x+0.2) + "
            "0.25*cos(3*x-0.4) + "
            "exp(-((x-1.1)**2)/1.8) - 0.08*x"
        ),
        target_latex=(
            r"0.7\sin(1.3x+0.2)+0.25\cos(3x-0.4)+"
            r"e^{-\frac{(x-1.1)^2}{1.8}}-0.08x"
        ),

        domain_min=-10,
        domain_max=10,

        range_min=-5,
        range_max=5,

    ),

    Challenge(
        challenge_date=date(2026, 9, 14),

        target_expr=(
            "0.62*cos(0.8*x-0.5) + "
            "0.18*sin(2.7*x+0.1) + "
            "exp(-((x+1.4)**2)/2.4) + 0.04*x "
            "- 0.15*abs(x-2.0)"
        ),
        target_latex=(
            r"0.62\cos(0.8x-0.5)+0.18\sin(2.7x+0.1)+"
            r"e^{-\frac{(x+1.4)^2}{2.4}}+0.04x-0.15|x-2|"
        ),

        domain_min=-10,
        domain_max=10,

        range_min=-3,
        range_max=3,
    ),

    Challenge(
        challenge_date=date(2026, 9, 15),

        target_expr=(
            "0.55*sin(0.9*x-0.3) + "
            "0.22*cos(2.4*x+0.6) + "
            "exp(-((x-0.8)**2)/1.6) - 0.06*x "
            "+ 0.12*sqrt((x+4.5)/2)"
        ),
        target_latex=(
            r"0.55\sin(0.9x-0.3)+0.22\cos(2.4x+0.6)+"
            r"e^{-\frac{(x-0.8)^2}{1.6}}-0.06x+"
            r"0.12\sqrt{\frac{x+4.5}{2}}"
        ),

        domain_min=-4,
        domain_max=4,

        range_min=-1,
        range_max=2,
    ),

    Challenge(
        challenge_date=date(2026, 9, 16),
        target_expr=(
            "0.45*sin(1.1*x+0.4) + 0.2*cos(2.8*x-0.2) + "
            "exp(-((x-2.2)**2)/1.4) + 0.12*log(x+8) - 0.05*x"
        ),
        target_latex=(
            r"0.45\sin(1.1x+0.4)+0.2\cos(2.8x-0.2)+"
            r"e^{-\frac{(x-2.2)^2}{1.4}}+0.12\log(x+8)-0.05x"
        ),
        domain_min=-7,
        domain_max=7,
        range_min=-3,
        range_max=3,
    ),

    Challenge(
        challenge_date=date(2026, 9, 17),
        target_expr=(
            "0.3*sin(1.2*x) + 0.4*cos(0.6*x-0.7) + "
            "0.16*exp(-((x+0.7)**2)/3) + 0.08*sqrt(x+7) "
            "+ 0.04*abs(x-1.5)"
        ),
        target_latex=(
            r"0.3\sin(1.2x)+0.4\cos(0.6x-0.7)+"
            r"0.16e^{-\frac{(x+0.7)^2}{3}}+0.08\sqrt{x+7}+"
            r"0.04|x-1.5|"
        ),
        domain_min=-6,
        domain_max=6,
        range_min=-2,
        range_max=3,
    ),

    Challenge(
        challenge_date=date(2026, 9, 18),
        target_expr=(
            "0.52*sin(0.75*x-0.2) - 0.17*cos(3.1*x) + "
            "0.11*log(x+10) + exp(-((x+2.5)**2)/2.2) "
            "+ 0.03*x"
        ),
        target_latex=(
            r"0.52\sin(0.75x-0.2)-0.17\cos(3.1x)+"
            r"0.11\log(x+10)+e^{-\frac{(x+2.5)^2}{2.2}}+0.03x"
        ),
        domain_min=-9,
        domain_max=9,
        range_min=-3,
        range_max=3,
    ),

    Challenge(
        challenge_date=date(2026, 9, 19),
        target_expr=(
            "0.38*cos(1.4*x+0.3) + 0.24*sin(2.2*x-0.8) + "
            "0.2*sqrt((x+6)/2) - 0.09*abs(x-0.5) "
            "+ exp(-((x-1.8)**2)/1.1)"
        ),
        target_latex=(
            r"0.38\cos(1.4x+0.3)+0.24\sin(2.2x-0.8)+"
            r"0.2\sqrt{\frac{x+6}{2}}-0.09|x-0.5|+"
            r"e^{-\frac{(x-1.8)^2}{1.1}}"
        ),
        domain_min=-5,
        domain_max=5,
        range_min=-3,
        range_max=3,
    ),

    Challenge(
        challenge_date=date(2026, 9, 20),
        target_expr=(
            "0.6*sin(0.5*x+0.1) + 0.13*cos(3.6*x+0.5) + "
            "0.14*log(x+9) + 0.18*exp(-((x-3.0)**2)/2.8) "
            "- 0.045*x"
        ),
        target_latex=(
            r"0.6\sin(0.5x+0.1)+0.13\cos(3.6x+0.5)+"
            r"0.14\log(x+9)+0.18e^{-\frac{(x-3)^2}{2.8}}-0.045x"
        ),
        domain_min=-8,
        domain_max=8,
        range_min=-3,
        range_max=3,
    ),
]


def main():
    with SessionLocal() as db:
        for challenge in CHALLENGES:
            existing = db.scalar(
                select(Challenge).where(
                    Challenge.challenge_date
                    == challenge.challenge_date
                )
            )

            if existing:
                existing.target_expr = challenge.target_expr
                existing.target_latex = challenge.target_latex
                existing.domain_min = challenge.domain_min
                existing.domain_max = challenge.domain_max
                existing.range_min = challenge.range_min
                existing.range_max = challenge.range_max
                print("Updated:", challenge.challenge_date)
                continue

            db.add(challenge)

            print(
                "Added:",
                challenge.challenge_date,
            )

        db.commit()


if __name__ == "__main__":
    main()
