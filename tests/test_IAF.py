import pytest
import os
import torch
import numpy as np
import shutil

from copy import deepcopy
from torch.optim import Adam

from pythae.models.base.base_utils import ModelOutput
from pythae.models.normalizing_flows import IAF, IAFConfig
from pythae.models.normalizing_flows import NFModel
from pythae.data.datasets import BaseDataset


from pythae.trainers import BaseTrainer, BaseTrainerConfig
from pythae.pipelines import TrainingPipeline

PATH = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(params=[IAFConfig(n_hidden_in_made=10), IAFConfig(n_made_blocks=2)])
def model_configs_no_input_output_dim(request):
    return request.param


@pytest.fixture(
    params=[
        IAFConfig(
            input_dim=(1, 8, 2), n_made_blocks=2, n_hidden_in_made=1, hidden_size=3
        ),
        IAFConfig(
            input_dim=(1, 2, 18),
            hidden_size=12,
            include_batch_norm=True,
            n_made_blocks=1,
        ),
    ]
)
def model_configs(request):
    return request.param


class Test_Model_Building:
    def test_build_model(self, model_configs):
        model = IAF(model_configs)
        assert all(
            [
                model.input_dim == np.prod(model_configs.input_dim),
            ]
        )

    def test_raises_no_input_output_dim(self, model_configs_no_input_output_dim):
        with pytest.raises(AttributeError):
            model = IAF(model_configs_no_input_output_dim)


class Test_Model_Saving:
    def test_creates_saving_path(self, tmpdir, model_configs):
        tmpdir.mkdir("saving")
        dir_path = os.path.join(tmpdir, "saving")
        model = IAF(model_configs)
        model.save(dir_path=dir_path)

        dir_path = None
        model = IAF(model_configs)
        with pytest.raises(TypeError) or pytest.raises(FileNotFoundError):
            model.save(dir_path=dir_path)

    def test_default_model_saving(self, tmpdir, model_configs):

        tmpdir.mkdir("dummy_folder")
        dir_path = dir_path = os.path.join(tmpdir, "dummy_folder")

        model = IAF(model_configs)

        rnd_key = list(model.state_dict().keys())[0]
        model.state_dict()[rnd_key][0] = 0

        model.save(dir_path=dir_path)

        assert set(os.listdir(dir_path)) == set(["model_config.json", "model.pt"])

        # reload model
        model_rec = IAF.load_from_folder(dir_path)

        # check configs are the same
        assert model_rec.model_config.__dict__ == model.model_config.__dict__

        assert all(
            [
                torch.equal(model_rec.state_dict()[key], model.state_dict()[key])
                for key in model.state_dict().keys()
            ]
        )

    def test_raises_missing_files(self, tmpdir, model_configs):

        tmpdir.mkdir("dummy_folder")
        dir_path = dir_path = os.path.join(tmpdir, "dummy_folder")

        model = IAF(
            model_configs,
        )

        rnd_key = list(model.state_dict().keys())[0]
        model.state_dict()[rnd_key][0] = 0

        model.save(dir_path=dir_path)

        os.remove(os.path.join(dir_path, "model.pt"))

        # check raises model.pt is missing
        with pytest.raises(FileNotFoundError):
            model_rec = IAF.load_from_folder(dir_path)

        torch.save({"wrong_key": 0.0}, os.path.join(dir_path, "model.pt"))
        # check raises wrong key in model.pt
        with pytest.raises(KeyError):
            model_rec = IAF.load_from_folder(dir_path)

        os.remove(os.path.join(dir_path, "model_config.json"))

        # check raises model_config.json is missing
        with pytest.raises(FileNotFoundError):
            model_rec = IAF.load_from_folder(dir_path)


class Test_Model_forward:
    @pytest.fixture
    def demo_data(self):
        data = torch.load(os.path.join(PATH, "data/mnist_clean_train_dataset_sample"))[
            :
        ]
        return data  # This is an extract of 3 data from MNIST (unnormalized) used to test custom architecture

    @pytest.fixture
    def iaf(self, model_configs, demo_data):
        model_configs.input_dim = tuple(demo_data["data"][0].shape)
        return IAF(model_configs)

    def test_model_train_output(self, iaf, demo_data):

        iaf.train()
        out = iaf(demo_data["data"])

        assert isinstance(out, ModelOutput)

        assert set(["out", "log_abs_det_jac"]) == set(out.keys())

        assert out.out.shape[0] == demo_data["data"].shape[0]
        assert out.log_abs_det_jac.shape == (demo_data["data"].shape[0],)
        assert out.out.shape[1:] == np.prod(
            iaf.model_config.input_dim
        )  # input_dim = output_dim

        assert torch.equal(out.log_abs_det_jac, out.log_abs_det_jac)  # check no NaN

        out = iaf.inverse(out.out)

        assert isinstance(out, ModelOutput)

        assert set(["out", "log_abs_det_jac"]) == set(out.keys())

        assert out.out.shape[0] == demo_data["data"].shape[0]
        assert out.log_abs_det_jac.shape == (demo_data["data"].shape[0],)
        assert out.out.shape[1:] == np.prod(iaf.model_config.input_dim)

        assert torch.equal(out.log_abs_det_jac, out.log_abs_det_jac)  # check no NaN


@pytest.mark.slow
class Test_IAF_Training:
    @pytest.fixture
    def train_dataset(self):
        return BaseDataset(torch.randn(3, 12), torch.ones(3))

    @pytest.fixture(
        params=[BaseTrainerConfig(num_epochs=3, steps_saving=2, learning_rate=1e-5)]
    )
    def training_configs(self, tmpdir, request):
        tmpdir.mkdir("dummy_folder")
        dir_path = os.path.join(tmpdir, "dummy_folder")
        request.param.output_dir = dir_path
        return request.param

    @pytest.fixture(
        params=[
            IAFConfig(
                input_dim=(12,), n_made_blocks=3, n_hidden_in_made=3, hidden_size=134
            ),
        ]
    )
    def model_configs(self, request):
        return request.param

    @pytest.fixture
    def iaf(self, model_configs):
        model = IAF(model_configs)
        return model

    @pytest.fixture()
    def prior(self, model_configs, request):

        device = "cuda" if torch.cuda.is_available() else "cpu"

        return torch.distributions.MultivariateNormal(
            torch.zeros(np.prod(model_configs.input_dim)).to(device),
            torch.eye(np.prod(model_configs.input_dim)).to(device),
        )

    @pytest.fixture(params=[Adam])
    def optimizers(self, request, iaf, training_configs):
        if request.param is not None:
            optimizer = request.param(
                iaf.parameters(), lr=training_configs.learning_rate
            )

        else:
            optimizer = None

        return optimizer

    def test_iaf_train_step(
        self, iaf, prior, train_dataset, training_configs, optimizers
    ):

        nf_model = NFModel(prior=prior, flow=iaf)

        trainer = BaseTrainer(
            model=nf_model,
            train_dataset=train_dataset,
            training_config=training_configs,
            optimizer=optimizers,
        )

        start_model_state_dict = deepcopy(trainer.model.state_dict())

        step_1_loss = trainer.train_step(epoch=1)

        step_1_model_state_dict = deepcopy(trainer.model.state_dict())

        # check that weights were updated
        assert not all(
            [
                torch.equal(start_model_state_dict[key], step_1_model_state_dict[key])
                for key in start_model_state_dict.keys()
            ]
        )

    def test_iaf_eval_step(
        self, iaf, prior, train_dataset, training_configs, optimizers
    ):

        nf_model = NFModel(prior=prior, flow=iaf)

        trainer = BaseTrainer(
            model=nf_model,
            train_dataset=train_dataset,
            eval_dataset=train_dataset,
            training_config=training_configs,
            optimizer=optimizers,
        )

        start_model_state_dict = deepcopy(trainer.model.state_dict())

        step_1_loss = trainer.eval_step(epoch=1)

        step_1_model_state_dict = deepcopy(trainer.model.state_dict())

        # check that weights were updated
        assert all(
            [
                torch.equal(start_model_state_dict[key], step_1_model_state_dict[key])
                for key in start_model_state_dict.keys()
            ]
        )

    def test_iaf_main_train_loop(
        self, iaf, prior, train_dataset, training_configs, optimizers
    ):

        nf_model = NFModel(prior=prior, flow=iaf)

        trainer = BaseTrainer(
            model=nf_model,
            train_dataset=train_dataset,
            training_config=training_configs,
            optimizer=optimizers,
        )

        start_model_state_dict = deepcopy(trainer.model.state_dict())

        trainer.train()

        step_1_model_state_dict = deepcopy(trainer.model.state_dict())

        # check that weights were updated
        assert not all(
            [
                torch.equal(start_model_state_dict[key], step_1_model_state_dict[key])
                for key in start_model_state_dict.keys()
            ]
        )

    def test_checkpoint_saving(
        self, tmpdir, iaf, prior, train_dataset, training_configs, optimizers
    ):

        dir_path = training_configs.output_dir

        nf_model = NFModel(prior=prior, flow=iaf)

        trainer = BaseTrainer(
            model=nf_model,
            train_dataset=train_dataset,
            training_config=training_configs,
            optimizer=optimizers,
        )

        # Make a training step
        step_1_loss = trainer.train_step(epoch=1)

        model = deepcopy(trainer.model.flow)
        optimizer = deepcopy(trainer.optimizer)

        trainer.save_checkpoint(dir_path=dir_path, epoch=0, model=model)

        checkpoint_dir = os.path.join(dir_path, "checkpoint_epoch_0")

        assert os.path.isdir(checkpoint_dir)

        files_list = os.listdir(checkpoint_dir)

        assert set(["model.pt", "optimizer.pt", "training_config.json"]).issubset(
            set(files_list)
        )

        model_rec_state_dict = torch.load(os.path.join(checkpoint_dir, "model.pt"))[
            "model_state_dict"
        ]

        assert all(
            [
                torch.equal(
                    model_rec_state_dict[key].cpu(), model.state_dict()[key].cpu()
                )
                for key in model.state_dict().keys()
            ]
        )

        # check reload full model
        model_rec = IAF.load_from_folder(os.path.join(checkpoint_dir))

        assert all(
            [
                torch.equal(
                    model_rec.state_dict()[key].cpu(), model.state_dict()[key].cpu()
                )
                for key in model.state_dict().keys()
            ]
        )

        optim_rec_state_dict = torch.load(os.path.join(checkpoint_dir, "optimizer.pt"))

        assert all(
            [
                dict_rec == dict_optimizer
                for (dict_rec, dict_optimizer) in zip(
                    optim_rec_state_dict["param_groups"],
                    optimizer.state_dict()["param_groups"],
                )
            ]
        )

        assert all(
            [
                dict_rec == dict_optimizer
                for (dict_rec, dict_optimizer) in zip(
                    optim_rec_state_dict["state"], optimizer.state_dict()["state"]
                )
            ]
        )

    def test_checkpoint_saving_during_training(
        self, tmpdir, iaf, prior, train_dataset, training_configs, optimizers
    ):
        #
        target_saving_epoch = training_configs.steps_saving

        dir_path = training_configs.output_dir

        nf_model = NFModel(prior=prior, flow=iaf)

        trainer = BaseTrainer(
            model=nf_model,
            train_dataset=train_dataset,
            training_config=training_configs,
            optimizer=optimizers,
        )

        model = deepcopy(trainer.model.flow)

        trainer.train()

        training_dir = os.path.join(
            dir_path, f"IAF_training_{trainer._training_signature}"
        )
        assert os.path.isdir(training_dir)

        checkpoint_dir = os.path.join(
            training_dir, f"checkpoint_epoch_{target_saving_epoch}"
        )

        assert os.path.isdir(checkpoint_dir)

        files_list = os.listdir(checkpoint_dir)

        # check files
        assert set(["model.pt", "optimizer.pt", "training_config.json"]).issubset(
            set(files_list)
        )

        model_rec_state_dict = torch.load(os.path.join(checkpoint_dir, "model.pt"))[
            "model_state_dict"
        ]

        assert not all(
            [
                torch.equal(model_rec_state_dict[key], model.state_dict()[key])
                for key in model.state_dict().keys()
            ]
        )

    def test_final_model_saving(
        self, tmpdir, iaf, prior, train_dataset, training_configs, optimizers
    ):

        dir_path = training_configs.output_dir

        nf_model = NFModel(prior=prior, flow=iaf)

        trainer = BaseTrainer(
            model=nf_model,
            train_dataset=train_dataset,
            training_config=training_configs,
            optimizer=optimizers,
        )

        trainer.train()

        model = deepcopy(trainer._best_model.flow)

        training_dir = os.path.join(
            dir_path, f"IAF_training_{trainer._training_signature}"
        )
        assert os.path.isdir(training_dir)

        final_dir = os.path.join(training_dir, f"final_model")
        assert os.path.isdir(final_dir)

        files_list = os.listdir(final_dir)

        assert set(["model.pt", "model_config.json", "training_config.json"]).issubset(
            set(files_list)
        )

        # check reload full model
        model_rec = IAF.load_from_folder(os.path.join(final_dir))

        assert all(
            [
                torch.equal(
                    model_rec.state_dict()[key].cpu(), model.state_dict()[key].cpu()
                )
                for key in model.state_dict().keys()
            ]
        )

    def test_iaf_training_pipeline(
        self, tmpdir, iaf, prior, train_dataset, training_configs
    ):

        dir_path = training_configs.output_dir

        nf_model = NFModel(prior=prior, flow=iaf)

        # build pipeline
        pipeline = TrainingPipeline(model=nf_model, training_config=training_configs)

        assert pipeline.training_config.__dict__ == training_configs.__dict__

        # Launch Pipeline
        pipeline(
            train_data=train_dataset.data,  # gives tensor to pipeline
            eval_data=train_dataset.data,  # gives tensor to pipeline
        )

        model = deepcopy(pipeline.trainer._best_model.flow)

        training_dir = os.path.join(
            dir_path, f"IAF_training_{pipeline.trainer._training_signature}"
        )
        assert os.path.isdir(training_dir)

        final_dir = os.path.join(training_dir, f"final_model")
        assert os.path.isdir(final_dir)

        files_list = os.listdir(final_dir)

        assert set(["model.pt", "model_config.json", "training_config.json"]).issubset(
            set(files_list)
        )

        # check reload full model
        model_rec = IAF.load_from_folder(os.path.join(final_dir))

        assert all(
            [
                torch.equal(
                    model_rec.state_dict()[key].cpu(), model.state_dict()[key].cpu()
                )
                for key in model.state_dict().keys()
            ]
        )
