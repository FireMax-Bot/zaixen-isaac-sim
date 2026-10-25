# Abnormal data - 17 attacks

One folder per attack (`01_noise` ... `17_service_abuse`). Every run is 90 seconds: **30 s normal, 30 s attack (30-60 s), 30 s normal**.
Each attack was run with 10, 20 and 30 other cars, seeds 1, 2, 3. Attacks that can be weaker or stronger have 3 strength levels (L1 weakest, L3 strongest); the others have one setting.

Strength levels exist for: noise, bias/drift, jump, delay, drop, duplicate, clock skew, flood.

The 17 attacks in plain words:

1. noise - readings get extra jitter, like a shaky hand.
2. bias/drift - readings slide off the truth, by a steady amount or slowly growing.
3. jump - one sudden impossible value.
4. freeze - the sensor gets stuck repeating its last value.
5. replay - old real data from a few seconds ago is played back.
6. false contact - a crash signal appears when nothing was hit. (limited: the car never really collides yet)
7. missed contact - a real crash is hidden. (limited: the car never really collides yet)
8. delay - every message arrives late.
9. drop - some messages never arrive.
10. duplicate - the same message is sent several times.
11. clock skew - the values are fine but the timestamps are wrong.
12. flood - the wire is swamped with huge numbers of messages.
13. spoof - a stranger pretends to be the real sensor and sends fake readings.
14. unauthorized node - a program that should not exist joins the system.
15. eavesdropping - a program secretly listens; no values change, only the listener count goes up.
16. parameter tampering - someone changes a program's settings behind its back. (weak: this is a target we added on purpose)
17. service abuse - someone spams a program's request function. (weak: this is a target we added on purpose)

Four of them are limited: 6 and 7 (the car never really collides, so the contact signal is always 0.0 in normal driving) and 16 and 17 (weak: targets we added on purpose).
Read `../AI_TEAM_GUIDE.md` first.
