import omni.usd
from pxr import Usd, UsdGeom, Gf

stage = omni.usd.get_context().get_stage()

if stage.GetPrimAtPath("/World/Ego").IsValid():
    stage.RemovePrim("/World/Ego")
# clear any stray session-layer override left over from a previous (possibly
# corrupted) physics run at this same path
session = stage.GetSessionLayer()
prev_target = stage.GetEditTarget()
stage.SetEditTarget(Usd.EditTarget(session))
if stage.GetPrimAtPath("/World/Ego").IsValid():
    stage.RemovePrim("/World/Ego")
stage.SetEditTarget(prev_target)

ego_path = "/World/Ego/leatherback"
asset_url = "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/6.0/Isaac/Samples/ROS2/Robots/leatherback_ROS.usd"

# explicit Xform type on the parent -- an implicit ancestor prim (created only via
# DefinePrim on the nested child path) ends up with an empty typeName, which makes
# USD's IsA<UsdGeomXformable> check fail and silently ignore its transform ops.
ego_parent = stage.DefinePrim("/World/Ego", "Xform")
ego_prim = stage.DefinePrim(ego_path, "Xform")
ego_prim.GetReferences().AddReference(asset_url)

xf = UsdGeom.Xformable(ego_parent)
xf.ClearXformOpOrder()
xf.AddTranslateOp().Set(Gf.Vec3d(-13.0, -0.5, 0.05))
xf.AddRotateZOp().Set(0.0)

# NOTE: leave every RigidBodyAPI on the reference at its default (enabled). Disabling
# individual rigid bodies breaks the asset's own suspension joints -- PhysX refuses to
# create a joint between two bodies it now sees as static ("PhysicsUSD: CreateJoint -
# cannot create a joint between static bodies"), which errors on every single joint in
# the articulation the moment you press Play. The articulation is physically stable on
# its own (ground has a collider, so it settles under gravity instead of falling through)
# as long as it's referenced fresh with no leftover corrupted per-body transforms.
print("STEP4 OK - ego placed at /World/Ego, physics enabled")
