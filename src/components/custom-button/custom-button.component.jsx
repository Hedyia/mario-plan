import React from "react";

const CustomButton = ({ title }) => {
  return (
    <div className="input-field">
      <button className="btn pink lighten-1 z-depth-0">{title}</button>
    </div>
  );
};

export default CustomButton;
