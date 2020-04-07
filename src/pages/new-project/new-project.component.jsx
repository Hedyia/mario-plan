import React, { Component } from "react";
import FormInput from "../../components/form-input/form-input.component";
import CustomButton from "../../components/custom-button/custom-button.component";
import TextArea from "../../components/text-area/text-area.component";

class NewProject extends Component {
  state = {
    title: "",
    content: "",
  };

  handleChange = ({ target }) => {
    const name = target.name;
    const value = target.value;
    this.setState({
      [name]: value,
    });
  };
  handleSubmit = (e) => {
    e.preventDefault();
    console.log(this.state);
  };
  render() {
    return (
      <div className="container">
        <form action={this.handleSubmit} className="white">
          <h5 className="grey-text text-darken-3">New Project</h5>

          <FormInput
            name="title"
            title="Title"
            type="text"
            value={this.state.title}
            handleChange={this.handleChange}
          />
          <TextArea
            title="Project Content"
            handleChange={this.handleChange}
            name="content"
            value={this.state.content}
          />
          <CustomButton title="create" />
        </form>
      </div>
    );
  }
}

export default NewProject;
