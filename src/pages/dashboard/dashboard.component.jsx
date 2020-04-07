import React, { Component } from "react";
import ProjectList from "../../components/project-list/project-list.component";

class Dashboard extends Component {
  state = {};
  render() {
    return (
      <div className="dashboard container">
        <div className="row">
          <div className="col s12 m6">
            <ProjectList />
          </div>
          <div className="col s12 m5 offset-m1">
            <h1>Notifications</h1>
          </div>
        </div>
      </div>
    );
  }
}

export default Dashboard;
