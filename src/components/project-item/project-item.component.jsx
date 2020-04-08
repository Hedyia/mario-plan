import React from "react";

const ProjectItem = ({ title, content, createdAt }) => {
  return (
    <div className="card z-depth-0 project-summary">
      <div className="card-content grey-text text-darken-3">
        <span className="card-title">{title}</span>
        <p>{content}</p>
        <p className="grey-text">{createdAt}</p>
      </div>
    </div>
  );
};

export default ProjectItem;
