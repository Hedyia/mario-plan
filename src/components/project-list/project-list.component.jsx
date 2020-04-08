import React from "react";
import ProjectItem from "../project-item/project-item.component";
import { connect } from "react-redux";
const ProjectList = ({ projects }) => {
  return (
    <div className="section project-list">
      {projects.map((project) => (
        <ProjectItem {...project} />
      ))}
    </div>
  );
};

const mapStateToProps = (state) => ({
  projects: state.project.projects,
});
export default connect(mapStateToProps)(ProjectList);
