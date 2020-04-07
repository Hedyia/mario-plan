import React from "react";
import { Switch, Route } from "react-router-dom";
import Navbar from "./components/navbar/navbar.component";
import Dashboard from "./pages/dashboard/dashboard.component";
import ProjectDetail from "./pages/project-detail/project-detail.component";
import Auth from "./pages/auth/auth.component";
import NewProject from "./pages/new-project/new-project.component";

function App() {
  return (
    <div>
      <Navbar />
      <Switch>
        <Route path="/" exact component={Dashboard} />
        <Route path="/project/:id" component={ProjectDetail} />
        <Route path="/auth" component={Auth} />
        <Route path="/new-project" component={NewProject} />
      </Switch>
    </div>
  );
}

export default App;
