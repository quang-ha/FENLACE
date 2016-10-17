from dolfin import *
from dolfin_adjoint import *
import pyipopt
import numpy as np
import math as math

parameters["reorder_dofs_serial"] = False

#mesh = UnitSquareMesh(30,60)
#File("linear_elasticity_mesh.xml") << mesh
mesh = Mesh("xmlmesh.xml")

V = VectorFunctionSpace(mesh, "CG", 1) # displacement
M = FunctionSpace(mesh, "CG", 1)       # mu, control space
lam = Constant(1.0)

g_np = np.loadtxt("measuredDisp_1col.txt")
u_m = Function(V)
u_m.vector().set_local( g_np )
alpha = 1e-8
bc_coord = np.loadtxt("bc_coord.txt");
bc_disp = np.loadtxt("bc_disp.txt");
#T = as_matrix( ((0, 0), (0, 1)) )

def forward(mu):
  class PinPoint(SubDomain):
    def __init__(self,p):
      self.p = p
      SubDomain.__init__(self)
    def inside(self, x, on_boundary):
      return np.linalg.norm(x-self.p)<1e-8

  v = TestFunction(V)
  u = Function(V, name="State")
  F = inner(mu/2 * (grad(v)+grad(v).T), grad(u)+grad(u).T)*dx + lam*inner(div(v),div(u))*dx 
  bc = []
  for i in xrange(0, len(bc_coord)):
    if bc_disp[i,0] == 1:
      bc_0 = DirichletBC(V.sub(0), bc_disp[i,1], PinPoint([bc_coord[i,0],bc_coord[i,1]]), "pointwise")
      bc.append(bc_0)
    if bc_disp[i,2] == 1:
      bc_1 = DirichletBC(V.sub(1), bc_disp[i,3], PinPoint([bc_coord[i,0],bc_coord[i,1]]), "pointwise")
      bc.append(bc_1)
  solve(F == 0, u,  bc)
  return u

mu= interpolate(Constant(1), M, name="Control")
p = interpolate(Constant((1.0,1.0)), V)
b = interpolate(Constant((1.0,1.0)), V)
for it in xrange(20):
  adj_reset()

  u = forward(mu)

  output = File("output/output_iterations_final.pvd")
  mu_viz = Function(M, name="ControlVisualization")
  def eval_cb(j, mu):
    mu_viz.assign(mu)
    output << mu_viz

# H1 regularization
#  J = Functional((0.5*inner((u-u_m),u-u_m))*dx + 0.5*alpha*inner(grad(mu),grad(mu))*dx)
# smooth TVD regularization
#  J = Functional((0.5*inner((u-u_m),u-u_m))*dx + 0.5*alpha*sqrt(inner(grad(mu),grad(mu)) + 1e-3**2)*dx )
# split Bregman TVD regularization
  J = Functional((0.5*inner((u-u_m),u-u_m))*dx + 0.5*alpha*inner(grad(mu)-p+b,grad(mu)-p+b)*dx )
  mu_c = Control(mu)
  J_rf = ReducedFunctional(J, mu_c, eval_cb_post=eval_cb)

# scipy optimizer
  mu_opt = minimize(J_rf, bounds=(1.0, 10.0), options={"gtol":1e-16, "maxiter":3, "ftol":1e-16}) 
  mu.assign(mu_opt)

# split Bregman update p and b
  def shrink(x,x_,r):
    if x_-r > 0: return x/x_ * (x_-r)
    else: return 0
  mu_grad = project(grad(mu),V)
  mu_grad_tmp = mu_grad.vector()[:]
  b_tmp = b.vector()[:]
  p_tmp = p.vector()[:]
  length = len(mu_grad_tmp) / 2
  for i in xrange(length):
    x_tmp = [mu_grad_tmp[i]+b_tmp[i], mu_grad_tmp[i+length]+b_tmp[i+length]]
    x_tmp_mag = math.sqrt( x_tmp[0]**2 + x_tmp[1]**2 )
    p_tmp[i]        = shrink(x_tmp[0], x_tmp_mag, 1/alpha)
    p_tmp[i+length] = shrink(x_tmp[1], x_tmp_mag, 1/alpha)
  p.vector().set_local(p_tmp.array())
  b_ttmp = b_tmp + mu_grad_tmp - p.vector()[:]
  b.vector().set_local(b_ttmp.array())
  
#ipopt optimizer
#  problem = MinimizationProblem(J_rf, bounds=(1.0,20.0))
#  parameters = {'maximum_iterations': 2}
#  solver = IPOPTSolver(problem, parameters=parameters)
#  mu_opt = solver.solve()
#  mu.assign(mu_opt)


'''
# TAO optimizer
problem = MinimizationProblem(J_rf)
parameters = { "monitor": None,
               "type": "blmvm",
               "bounds":(1.0, 20.0),
               "max_it": 300,
               #"subset_type": "matrixfree",
               "fatol": 1e-17,
               "frtol": 1e-17,
               "gatol": 1e-17,
               "grtol": 1e-17
             }
solver = TAOSolver(problem, parameters=parameters)
mu_opt = solver.solve()
'''




u_sol = project(u, V)
File("output/u_sol.pvd") << u_sol
File("output/u_m.pvd") << u_m

plot(mu_opt, interactive=True, title="mu_opt")
plot(u, interactive=True, title="u")
#plot(u+g, interactive=True, title="u+g")
plot(u_m, interactive=True, title="u_m")
